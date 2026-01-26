#!/usr/bin/env python3
"""Main entry point for satellite image collection.

Downloads Sentinel-1 SAR and Sentinel-2 optical imagery from Copernicus Data Space.
Tracks downloaded products to avoid duplicates.

Usage:
    # Normal run (via cron or manual)
    python src/download.py

    # Dry-run mode (search but don't download)
    python src/download.py --dry-run

    # Limit downloads for testing
    python src/download.py --limit 1

    # Verbose logging
    python src/download.py --verbose
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import load_config
from copernicus_client import CopernicusClient, Product


@dataclass
class RunOptions:
    """Runtime options from CLI arguments."""

    dry_run: bool = False
    limit: int | None = None
    verbose: bool = False


def parse_args() -> RunOptions:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Download Sentinel satellite imagery from Copernicus Data Space",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/download.py                  # Normal run
  python src/download.py --dry-run        # Search only, don't download
  python src/download.py --limit 1        # Download max 1 product per type
  python src/download.py --verbose        # Enable debug logging
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search for products but don't download them",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        help="Maximum number of products to download per type (SAR/optical)",
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


def setup_logging(log_file: str, verbose: bool = False) -> None:
    """Configure logging to both file and stdout."""
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger(__name__)


class StateManager:
    """Manages state of downloaded products to avoid duplicates."""

    def __init__(self, state_file: str):
        self.state_file = Path(state_file)
        self._state: dict[str, Any] = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Load state from file or create empty state."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load state file: %s. Starting fresh.", e)

        return {
            "downloaded_products": {},
            "last_run": None,
        }

    def _save_state(self) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

    def is_downloaded(self, product_id: str) -> bool:
        """Check if a product has already been downloaded."""
        return product_id in self._state["downloaded_products"]

    def mark_downloaded(self, product: Product, output_path: str) -> None:
        """Mark a product as downloaded."""
        self._state["downloaded_products"][product.id] = {
            "name": product.name,
            "collection": product.collection,
            "sensing_time": product.sensing_time.isoformat(),
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "path": output_path,
        }
        self._save_state()

    def update_last_run(self) -> None:
        """Update the last run timestamp."""
        self._state["last_run"] = datetime.now(timezone.utc).isoformat()
        self._save_state()


def get_output_path(product: Product, base_path: str, dry_run: bool = False) -> str:
    """Generate output path for a product organized by date.

    Args:
        product: The product to generate a path for.
        base_path: Base directory for downloads.
        dry_run: If True, don't create directories.

    Returns:
        Full path where the product should be saved.
    """
    date_str = product.sensing_time.strftime("%Y-%m-%d")
    output_dir = Path(base_path) / date_str

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Product name typically ends with .SAFE for Sentinel products
    filename = product.name
    if not filename.endswith(".zip"):
        filename = f"{filename}.zip"

    return str(output_dir / filename)


def process_products(
    client: CopernicusClient,
    products: list[Product],
    base_path: str,
    state: StateManager,
    product_type: str,
    options: RunOptions,
) -> tuple[int, int, int]:
    """Download products that haven't been downloaded yet.

    Args:
        client: Copernicus API client.
        products: List of products to process.
        base_path: Base directory for downloads.
        state: State manager for tracking downloads.
        product_type: Type label for logging (e.g., "SAR", "Optical").
        options: Runtime options (dry-run, limit, etc.).

    Returns:
        Tuple of (successful downloads, failed downloads, skipped count)
    """
    success_count = 0
    failure_count = 0
    skipped_count = 0

    for product in products:
        # Check if we've reached the limit
        if options.limit is not None and success_count >= options.limit:
            logger.info("Reached limit of %d downloads for %s", options.limit, product_type)
            break

        if state.is_downloaded(product.id):
            logger.info("Skipping already downloaded: %s", product.name)
            skipped_count += 1
            continue

        output_path = get_output_path(product, base_path, dry_run=options.dry_run)

        if options.dry_run:
            logger.info(
                "[DRY-RUN] Would download %s %s to %s (%.2f MB)",
                product_type,
                product.name,
                output_path,
                product.size_bytes / (1024 * 1024),
            )
            success_count += 1
            continue

        logger.info("Downloading %s %s to %s", product_type, product.name, output_path)

        if client.download_product(product, output_path):
            state.mark_downloaded(product, output_path)
            success_count += 1
        else:
            failure_count += 1

    return success_count, failure_count, skipped_count


def main(options: RunOptions | None = None) -> int:
    """Main entry point for satellite data collection.

    Args:
        options: Runtime options. If None, parsed from command line.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Parse CLI arguments if not provided
    if options is None:
        options = parse_args()

    # Load configuration
    copernicus_config, search_config, storage_config, download_config = load_config()

    # Setup logging
    setup_logging(storage_config.log_file, verbose=options.verbose)

    logger.info("=" * 60)
    logger.info("Starting satellite image collection")
    if options.dry_run:
        logger.info("DRY-RUN MODE: No files will be downloaded")
    if options.limit:
        logger.info("Limiting to %d products per type", options.limit)
    logger.info("=" * 60)

    # Validate credentials (not required for dry-run)
    if not options.dry_run:
        if not copernicus_config.username or not copernicus_config.password:
            logger.error("Missing Copernicus credentials!")
            logger.error("Set COPERNICUS_USER and COPERNICUS_PASSWORD environment variables.")
            return 1

    # Initialize state manager
    state = StateManager(storage_config.state_file)

    # Initialize client
    client = CopernicusClient(copernicus_config, search_config, download_config)

    try:
        # Authenticate (required even for dry-run to search)
        client.authenticate()

        # Search and download Sentinel-1 SAR products
        logger.info("-" * 40)
        logger.info("Processing Sentinel-1 SAR products")
        logger.info("-" * 40)

        sar_products = client.search_sentinel1()
        sar_success, sar_failure, sar_skipped = process_products(
            client,
            sar_products,
            storage_config.sar_base_path,
            state,
            "SAR",
            options,
        )

        # Search and download Sentinel-2 optical products
        logger.info("-" * 40)
        logger.info("Processing Sentinel-2 optical products")
        logger.info("-" * 40)

        optical_products = client.search_sentinel2()
        optical_success, optical_failure, optical_skipped = process_products(
            client,
            optical_products,
            storage_config.optical_base_path,
            state,
            "Optical",
            options,
        )

        # Update last run timestamp (skip in dry-run mode)
        if not options.dry_run:
            state.update_last_run()

        # Summary
        logger.info("=" * 60)
        logger.info("Collection complete%s", " (DRY-RUN)" if options.dry_run else "")
        action = "would download" if options.dry_run else "downloaded"
        logger.info(
            "SAR: %d %s, %d failed, %d skipped",
            sar_success, action, sar_failure, sar_skipped,
        )
        logger.info(
            "Optical: %d %s, %d failed, %d skipped",
            optical_success, action, optical_failure, optical_skipped,
        )
        logger.info("=" * 60)

        # Return non-zero if any downloads failed
        if sar_failure > 0 or optical_failure > 0:
            return 1

        return 0

    except Exception as e:
        logger.exception("Fatal error during collection: %s", e)
        return 1

    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
