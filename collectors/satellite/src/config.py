"""Configuration for satellite data collection."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class CopernicusConfig:
    """Copernicus Data Space API configuration."""

    # OAuth2 endpoints
    token_url: str = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

    # OData API endpoint
    odata_url: str = "https://catalogue.dataspace.copernicus.eu/odata/v1"

    # Download endpoint
    download_url: str = "https://download.dataspace.copernicus.eu/odata/v1"

    # Credentials from environment
    username: str = ""
    password: str = ""

    def __post_init__(self) -> None:
        self.username = os.environ.get("COPERNICUS_USER", "")
        self.password = os.environ.get("COPERNICUS_PASSWORD", "")


@dataclass
class SearchConfig:
    """Search parameters for satellite products."""

    # Stockholm/Mälaren region bounding box
    # Format: west, south, east, north
    # Covers: Enköping (west) to archipelago (east), Södertälje (south) to Uppsala (north)
    sweden_bbox: tuple[float, float, float, float] = (17.0, 59.0, 19.0, 60.0)

    # Search time window in hours
    lookback_hours: int = 48

    # Sentinel-1 parameters
    s1_product_type: str = "GRD"
    s1_polarization: str = "VV"
    s1_sensor_mode: str = "IW"
    s1_collection: str = "SENTINEL-1"

    # Sentinel-2 parameters
    s2_product_type: str = "S2MSI2A"  # L2A product
    s2_collection: str = "SENTINEL-2"
    s2_max_cloud_cover: float = 30.0  # Maximum cloud cover percentage


@dataclass
class StorageConfig:
    """Storage paths configuration."""

    # Base paths for data storage
    sar_base_path: str = "/data/sar"
    optical_base_path: str = "/data/optical"

    # State file for tracking downloaded products
    state_file: str = "/state/satellite_downloads.json"

    # Log file path
    log_file: str = "/logs/satellite-collector.log"


@dataclass
class DownloadConfig:
    """Download behavior configuration."""

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: int = 30

    # Download chunk size
    chunk_size: int = 8192

    # Request timeout in seconds
    request_timeout: int = 300

    # Token refresh margin (refresh before expiry)
    token_refresh_margin_seconds: int = 60


def load_config() -> tuple[CopernicusConfig, SearchConfig, StorageConfig, DownloadConfig]:
    """Load all configuration objects."""
    return (
        CopernicusConfig(),
        SearchConfig(),
        StorageConfig(),
        DownloadConfig(),
    )
