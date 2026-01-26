#!/usr/bin/env python3
"""Fetch weather observations from SMHI and store as JSON.

This script:
1. Fetches observations from configured weather stations
2. Calculates cold degree days for temperature data
3. Stores data organized by date

Usage:
    # Normal run (via cron or manual)
    python src/fetch.py

    # Dry-run mode (fetch but don't save)
    python src/fetch.py --dry-run

    # Limit to specific number of stations
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

from config import DATA_DIR, FREEZING_POINT, LOG_DIR, LOG_FILE, STATIONS
from smhi_client import SMHIClient, SMHIClientError


@dataclass
class RunOptions:
    """Runtime options from CLI arguments."""

    dry_run: bool = False
    limit: int | None = None
    verbose: bool = False


def parse_args() -> RunOptions:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Fetch weather observations from SMHI Open Data API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/fetch.py                  # Normal run
  python src/fetch.py --dry-run        # Fetch only, don't save files
  python src/fetch.py --limit 2        # Fetch max 2 stations
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
        help="Maximum number of stations to fetch",
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


def calculate_cold_degree_days(
    temperature_observations: list[dict],
) -> dict[str, float]:
    """Calculate cold degree days from temperature observations.

    Cold degree days (CDD) measure cumulative freezing. Each hour below
    freezing contributes (freezing_point - temp) / 24 to the daily total.

    Args:
        temperature_observations: List of observations with 'timestamp' and 'value'.

    Returns:
        Dictionary mapping date strings to cold degree day values.
    """
    # Group observations by date
    daily_temps: dict[str, list[float]] = {}

    for obs in temperature_observations:
        dt = datetime.fromisoformat(obs["timestamp"])
        date_str = dt.strftime("%Y-%m-%d")

        if date_str not in daily_temps:
            daily_temps[date_str] = []

        daily_temps[date_str].append(obs["value"])

    # Calculate CDD for each day
    cold_degree_days = {}

    for date_str, temps in daily_temps.items():
        # Calculate average temperature for the day
        avg_temp = sum(temps) / len(temps)

        # CDD is positive when temperature is below freezing
        if avg_temp < FREEZING_POINT:
            cdd = FREEZING_POINT - avg_temp
        else:
            cdd = 0.0

        cold_degree_days[date_str] = round(cdd, 2)

    return cold_degree_days


def save_station_data(
    station_id: int,
    station_info: dict,
    observations: dict[str, list[dict]],
    cold_degree_days: dict[str, float],
    logger: logging.Logger,
    dry_run: bool = False,
) -> None:
    """Save station observations to JSON files organized by date.

    Args:
        station_id: The weather station ID.
        station_info: Station metadata from config.
        observations: Dictionary of parameter observations.
        cold_degree_days: Calculated CDD values per date.
        logger: Logger instance.
        dry_run: If True, don't save files.
    """
    # Get the current date for organizing data
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Prepare station data
    station_data = {
        "station_id": station_id,
        "station_name": station_info["name"],
        "lakes": station_info["lakes"],
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "observations": observations,
        "cold_degree_days": cold_degree_days,
    }

    # Generate output path
    date_dir = DATA_DIR / today
    output_file = date_dir / f"station_{station_id}.json"

    if dry_run:
        # Count observations for summary
        obs_count = sum(len(obs) for obs in observations.values())
        logger.info(
            "[DRY-RUN] Would save station %d (%s) to %s (%d observations)",
            station_id,
            station_info["name"],
            output_file,
            obs_count,
        )
        return

    # Create date directory
    date_dir.mkdir(parents=True, exist_ok=True)

    # Save to JSON file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(station_data, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved data for station {station_id} to {output_file}")


def fetch_all_stations(logger: logging.Logger, options: RunOptions) -> dict[str, int]:
    """Fetch observations from all configured stations.

    Args:
        logger: Logger instance.
        options: Runtime options (dry-run, limit, etc.).

    Returns:
        Dictionary with success/failure counts.
    """
    client = SMHIClient()
    stats = {"success": 0, "failed": 0}

    stations_to_process = list(STATIONS.items())

    # Apply limit if specified
    if options.limit is not None:
        stations_to_process = stations_to_process[: options.limit]
        logger.info(f"Limiting to {options.limit} stations")

    for station_id, station_info in stations_to_process:
        logger.info(f"Fetching data for station {station_id} ({station_info['name']})")

        try:
            # Fetch all observations for this station
            observations = client.get_observations_for_station(station_id)

            # Calculate cold degree days from temperature data
            temp_obs = observations.get("temperature", [])
            cold_degree_days = calculate_cold_degree_days(temp_obs)

            # Save the data
            save_station_data(
                station_id,
                station_info,
                observations,
                cold_degree_days,
                logger,
                dry_run=options.dry_run,
            )

            stats["success"] += 1

        except SMHIClientError as e:
            logger.error(f"Failed to fetch data for station {station_id}: {e}")
            stats["failed"] += 1
        except Exception as e:
            logger.exception(f"Unexpected error for station {station_id}: {e}")
            stats["failed"] += 1

    return stats


def create_daily_summary(logger: logging.Logger) -> None:
    """Create a summary file combining all station data for today.

    Args:
        logger: Logger instance.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    date_dir = DATA_DIR / today

    if not date_dir.exists():
        logger.warning(f"No data directory for {today}")
        return

    # Collect all station files
    station_files = list(date_dir.glob("station_*.json"))

    if not station_files:
        logger.warning(f"No station files found for {today}")
        return

    # Build summary
    summary = {
        "date": today,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "station_count": len(station_files),
        "stations": {},
    }

    for station_file in station_files:
        with open(station_file, "r", encoding="utf-8") as f:
            station_data = json.load(f)

        station_id = station_data["station_id"]

        # Extract latest temperature if available
        temp_obs = station_data["observations"].get("temperature", [])
        latest_temp = temp_obs[-1]["value"] if temp_obs else None

        # Get today's CDD
        cdd_today = station_data["cold_degree_days"].get(today, 0.0)

        summary["stations"][str(station_id)] = {
            "name": station_data["station_name"],
            "lakes": station_data["lakes"],
            "latest_temperature": latest_temp,
            "cold_degree_days_today": cdd_today,
            "observation_counts": {
                param: len(obs)
                for param, obs in station_data["observations"].items()
            },
        }

    # Save summary
    summary_file = date_dir / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(f"Created daily summary at {summary_file}")


def main(options: RunOptions | None = None) -> int:
    """Main entry point for weather data collection.

    Args:
        options: Runtime options. If None, parsed from command line.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Parse CLI arguments if not provided
    if options is None:
        options = parse_args()

    logger = setup_logging(verbose=options.verbose)
    logger.info("Starting weather data collection")
    if options.dry_run:
        logger.info("DRY-RUN MODE: No files will be saved")
    if options.limit:
        logger.info(f"Limiting to {options.limit} stations")

    # Ensure data directory exists (skip in dry-run mode)
    if not options.dry_run:
        DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Fetch data from all stations
    stats = fetch_all_stations(logger, options)

    # Create daily summary (skip in dry-run mode)
    if not options.dry_run:
        create_daily_summary(logger)
    else:
        logger.info("[DRY-RUN] Would create daily summary")

    # Log results
    action = "would fetch" if options.dry_run else "fetched"
    logger.info(
        f"Collection complete{' (DRY-RUN)' if options.dry_run else ''}: "
        f"{stats['success']} {action}, {stats['failed']} failed"
    )

    # Return error code if any stations failed
    if stats["failed"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
