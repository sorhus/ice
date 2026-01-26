#!/usr/bin/env python3
"""Main entry point for satellite image collection.

Downloads Sentinel-1 SAR and Sentinel-2 optical imagery from Copernicus Data Space.
Tracks downloaded products to avoid duplicates.
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import load_config
from copernicus_client import CopernicusClient, Product

# Configure logging
def setup_logging(log_file: str) -> None:
    """Configure logging to both file and stdout."""
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
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


def get_output_path(product: Product, base_path: str) -> str:
    """Generate output path for a product organized by date."""
    date_str = product.sensing_time.strftime("%Y-%m-%d")
    output_dir = Path(base_path) / date_str
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
) -> tuple[int, int]:
    """Download products that haven't been downloaded yet.

    Returns:
        Tuple of (successful downloads, failed downloads)
    """
    success_count = 0
    failure_count = 0

    for product in products:
        if state.is_downloaded(product.id):
            logger.info("Skipping already downloaded: %s", product.name)
            continue

        output_path = get_output_path(product, base_path)
        logger.info("Downloading %s %s to %s", product_type, product.name, output_path)

        if client.download_product(product, output_path):
            state.mark_downloaded(product, output_path)
            success_count += 1
        else:
            failure_count += 1

    return success_count, failure_count


def main() -> int:
    """Main entry point for satellite data collection."""
    # Load configuration
    copernicus_config, search_config, storage_config, download_config = load_config()

    # Setup logging
    setup_logging(storage_config.log_file)

    logger.info("=" * 60)
    logger.info("Starting satellite image collection")
    logger.info("=" * 60)

    # Validate credentials
    if not copernicus_config.username or not copernicus_config.password:
        logger.error("Missing Copernicus credentials!")
        logger.error("Set COPERNICUS_USER and COPERNICUS_PASSWORD environment variables.")
        return 1

    # Initialize state manager
    state = StateManager(storage_config.state_file)

    # Initialize client
    client = CopernicusClient(copernicus_config, search_config, download_config)

    try:
        # Authenticate
        client.authenticate()

        # Search and download Sentinel-1 SAR products
        logger.info("-" * 40)
        logger.info("Processing Sentinel-1 SAR products")
        logger.info("-" * 40)

        sar_products = client.search_sentinel1()
        sar_success, sar_failure = process_products(
            client,
            sar_products,
            storage_config.sar_base_path,
            state,
            "SAR",
        )

        # Search and download Sentinel-2 optical products
        logger.info("-" * 40)
        logger.info("Processing Sentinel-2 optical products")
        logger.info("-" * 40)

        optical_products = client.search_sentinel2()
        optical_success, optical_failure = process_products(
            client,
            optical_products,
            storage_config.optical_base_path,
            state,
            "Optical",
        )

        # Update last run timestamp
        state.update_last_run()

        # Summary
        logger.info("=" * 60)
        logger.info("Collection complete")
        logger.info("SAR: %d downloaded, %d failed, %d skipped (already downloaded)",
                    sar_success, sar_failure, len(sar_products) - sar_success - sar_failure)
        logger.info("Optical: %d downloaded, %d failed, %d skipped (already downloaded)",
                    optical_success, optical_failure, len(optical_products) - optical_success - optical_failure)
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
