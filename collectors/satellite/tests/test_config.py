"""Tests for satellite collector configuration."""

import os
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_config.py", "/src"))

from config import (
    CopernicusConfig,
    DownloadConfig,
    SearchConfig,
    StorageConfig,
    load_config,
)


class TestCopernicusConfig:
    """Tests for CopernicusConfig dataclass."""

    def test_default_urls(self):
        """Config should have correct default API URLs."""
        config = CopernicusConfig()

        assert "identity.dataspace.copernicus.eu" in config.token_url
        assert "catalogue.dataspace.copernicus.eu" in config.odata_url
        assert "download.dataspace.copernicus.eu" in config.download_url

    def test_credentials_from_environment(self):
        """Config should load credentials from environment variables."""
        with patch.dict(os.environ, {
            "COPERNICUS_USER": "test_user",
            "COPERNICUS_PASSWORD": "test_pass",
        }):
            config = CopernicusConfig()

            assert config.username == "test_user"
            assert config.password == "test_pass"

    def test_missing_credentials(self):
        """Config should have empty credentials when env vars not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env vars if they exist
            os.environ.pop("COPERNICUS_USER", None)
            os.environ.pop("COPERNICUS_PASSWORD", None)

            config = CopernicusConfig()

            assert config.username == ""
            assert config.password == ""


class TestSearchConfig:
    """Tests for SearchConfig dataclass."""

    def test_default_sweden_bbox(self):
        """Search config should have correct Sweden bounding box."""
        config = SearchConfig()

        west, south, east, north = config.sweden_bbox
        # Sweden roughly spans 10.5°E to 24.2°E, 55.3°N to 69.1°N
        assert west == pytest.approx(10.5, abs=0.5)
        assert south == pytest.approx(55.3, abs=0.5)
        assert east == pytest.approx(24.2, abs=0.5)
        assert north == pytest.approx(69.1, abs=0.5)

    def test_sentinel1_params(self):
        """Search config should have correct Sentinel-1 parameters."""
        config = SearchConfig()

        assert config.s1_product_type == "GRD"
        assert config.s1_polarization == "VV"
        assert config.s1_sensor_mode == "IW"
        assert config.s1_collection == "SENTINEL-1"

    def test_sentinel2_params(self):
        """Search config should have correct Sentinel-2 parameters."""
        config = SearchConfig()

        assert "L2A" in config.s2_product_type or "2A" in config.s2_product_type
        assert config.s2_collection == "SENTINEL-2"
        assert 0 <= config.s2_max_cloud_cover <= 100

    def test_lookback_hours(self):
        """Search config should have reasonable lookback period."""
        config = SearchConfig()

        assert config.lookback_hours > 0
        assert config.lookback_hours <= 168  # Max 1 week


class TestStorageConfig:
    """Tests for StorageConfig dataclass."""

    def test_default_paths(self):
        """Storage config should have default paths."""
        config = StorageConfig()

        assert config.sar_base_path
        assert config.optical_base_path
        assert config.state_file
        assert config.log_file


class TestDownloadConfig:
    """Tests for DownloadConfig dataclass."""

    def test_retry_settings(self):
        """Download config should have valid retry settings."""
        config = DownloadConfig()

        assert config.max_retries >= 1
        assert config.retry_delay_seconds > 0

    def test_timeout_settings(self):
        """Download config should have valid timeout."""
        config = DownloadConfig()

        assert config.request_timeout > 0
        assert config.chunk_size > 0


class TestLoadConfig:
    """Tests for load_config function."""

    def test_returns_all_configs(self):
        """load_config should return all configuration objects."""
        configs = load_config()

        assert len(configs) == 4
        assert isinstance(configs[0], CopernicusConfig)
        assert isinstance(configs[1], SearchConfig)
        assert isinstance(configs[2], StorageConfig)
        assert isinstance(configs[3], DownloadConfig)
