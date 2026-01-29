#!/usr/bin/env python3
"""Fetch weather forecasts from SMHI and store as JSON.

This script:
1. Fetches forecasts from configured locations using SMHI PMP API
2. Parses and extracts relevant parameters (temperature, wind, precipitation)
3. Stores data organized by date and time

Usage:
    # Normal run (via cron or manual)
    python src/fetch.py

    # Dry-run mode (fetch but don't save)
    python src/fetch.py --dry-run

    # Limit to specific number of locations
    python src/fetch.py --limit 2

    # Verbose logging
    python src/fetch.py --verbose
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR, FORECAST_LOCATIONS, LOG_DIR, LOG_FILE
from smhi_forecast_client import SMHIForecastClient, SMHIForecastClientError


@dataclass
class RunOptions:
    """Runtime options from CLI arguments."""

    dry_run: bool = False
    limit: int | None = None
    verbose: bool = False


def parse_args() -> RunOptions:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch weather forecasts from SMHI PMP API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/fetch.py                  # Normal run
  python src/fetch.py --dry-run        # Fetch only, don't save files
  python src/fetch.py --limit 2        # Fetch max 2 locations
  python src/fetch.py --verbose        # Enable debug logging
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but don't save to files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Maximum number of locations to fetch",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (debug) logging",
    )

    args = parser.parse_args()
    return RunOptions(
        dry_run=args.dry_run,
        limit=args.limit,
        verbose=args.verbose,
    )


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging to both file and console."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger()
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(level)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_format = logging.Formatter("%(levelname)s - %(message)s")
    console_handler.setFormatter(console_format)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def save_forecast_data(
    location_id: str,
    location_info: dict,
    forecasts: list[dict],
    metadata: dict,
    logger: logging.Logger,
    dry_run: bool = False,
) -> None:
    """Save forecast data to JSON files organized by date and time.

    Args:
        location_id: The location identifier.
        location_info: Location metadata from config.
        forecasts: List of parsed forecast entries.
        metadata: Forecast metadata (approved_time, reference_time, etc.).
        logger: Logger instance.
        dry_run: If True, don't save files.
    """
    # Get current timestamp for organizing data
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d-%H")

    # Prepare forecast data
    forecast_data = {
        "location_id": location_id,
        "location_name": location_info["name"],
        "latitude": location_info["lat"],
        "longitude": location_info["lon"],
        "lakes": location_info["lakes"],
        "collected_at": now.isoformat(),
        "metadata": metadata,
        "forecasts": forecasts,
        "forecast_count": len(forecasts),
    }

    # Generate output path
    # Structure: /data/YYYY-MM-DD-HH/location_{location_id}.json
    timestamp_dir = DATA_DIR / timestamp
    output_file = timestamp_dir / f"location_{location_id}.json"

    if dry_run:
        logger.info(
            "[DRY-RUN] Would save location %s (%s) to %s (%d forecast hours)",
            location_id,
            location_info["name"],
            output_file,
            len(forecasts),
        )
        return

    # Create timestamp directory
    timestamp_dir.mkdir(parents=True, exist_ok=True)

    # Save to JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(forecast_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved forecast for {location_id} to {output_file}")


def fetch_all_forecasts(logger: logging.Logger, options: RunOptions) -> dict[str, int]:
    """Fetch forecasts from all configured locations.

    Args:
        logger: Logger instance.
        options: Runtime options (dry-run, limit, etc.).

    Returns:
        Dictionary with success/failure counts.
    """
    client = SMHIForecastClient()
    stats = {"success": 0, "failed": 0}

    locations_to_process = list(FORECAST_LOCATIONS.items())

    # Apply limit if specified
    if options.limit is not None:
        locations_to_process = locations_to_process[: options.limit]
        logger.info(f"Limiting to {options.limit} locations")

    for location_id, location_info in locations_to_process:
        logger.info(
            f"Fetching forecast for {location_id} ({location_info['name']}) "
            f"at lat={location_info['lat']}, lon={location_info['lon']}"
        )

        try:
            # Fetch raw forecast data
            forecast_data = client.get_forecast(
                lat=location_info["lat"],
                lon=location_info["lon"],
            )

            # Parse forecasts
            forecasts = client.parse_forecast(forecast_data)

            # Extract metadata
            metadata = client.get_forecast_metadata(forecast_data)

            # Save the data
            save_forecast_data(
                location_id,
                location_info,
                forecasts,
                metadata,
                logger,
                dry_run=options.dry_run,
            )

            stats["success"] += 1

        except SMHIForecastClientError as e:
            logger.error(f"Failed to fetch forecast for {location_id}: {e}")
            stats["failed"] += 1
        except Exception as e:
            logger.exception(f"Unexpected error for {location_id}: {e}")
            stats["failed"] += 1

    return stats


def create_forecast_summary(logger: logging.Logger) -> None:
    """Create a summary file combining all location forecasts for this run.

    Args:
        logger: Logger instance.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d-%H")
    timestamp_dir = DATA_DIR / timestamp

    if not timestamp_dir.exists():
        logger.warning(f"No data directory for {timestamp}")
        return

    # Collect all location files
    location_files = list(timestamp_dir.glob("location_*.json"))

    if not location_files:
        logger.warning(f"No location files found for {timestamp}")
        return

    # Build summary
    summary = {
        "timestamp": timestamp,
        "collected_at": now.isoformat(),
        "location_count": len(location_files),
        "locations": {},
    }

    for location_file in location_files:
        with open(location_file, "r", encoding="utf-8") as f:
            location_data = json.load(f)

        location_id = location_data["location_id"]

        # Get first forecast (earliest) if available
        forecasts = location_data.get("forecasts", [])
        first_forecast = forecasts[0] if forecasts else None
        first_temp = None
        if first_forecast:
            first_temp = first_forecast.get("parameters", {}).get("temperature")

        summary["locations"][location_id] = {
            "name": location_data["location_name"],
            "lakes": location_data["lakes"],
            "forecast_count": location_data["forecast_count"],
            "first_forecast_time": first_forecast["timestamp"] if first_forecast else None,
            "first_temperature": first_temp,
        }

    # Save summary
    summary_file = timestamp_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Created forecast summary at {summary_file}")


def main(options: RunOptions | None = None) -> int:
    """Main entry point for forecast data collection.

    Args:
        options: Runtime options. If None, parsed from command line.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Parse CLI arguments if not provided
    if options is None:
        options = parse_args()

    logger = setup_logging(verbose=options.verbose)
    logger.info("Starting forecast data collection")
    if options.dry_run:
        logger.info("DRY-RUN MODE: No files will be saved")
    if options.limit:
        logger.info(f"Limiting to {options.limit} locations")

    # Ensure data directory exists (skip in dry-run mode)
    if not options.dry_run:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch forecasts from all locations
    stats = fetch_all_forecasts(logger, options)

    # Create forecast summary (skip in dry-run mode)
    if not options.dry_run:
        create_forecast_summary(logger)
    else:
        logger.info("[DRY-RUN] Would create forecast summary")

    # Log results
    action = "would fetch" if options.dry_run else "fetched"
    logger.info(
        f"Collection complete{' (DRY-RUN)' if options.dry_run else ''}: "
        f"{stats['success']} {action}, {stats['failed']} failed"
    )

    # Return error code if any locations failed
    if stats["failed"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
