"""Tests for forecast collector configuration."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_config.py", "/src"))

from config import (
    DATA_DIR,
    FORECAST_LOCATIONS,
    FORECAST_PARAMETERS,
    LOG_DIR,
    LOG_FILE,
    SMHI_FORECAST_API_BASE,
)


class TestSMHIForecastConfig:
    """Tests for SMHI forecast API configuration."""

    def test_api_base_url(self):
        """Config should have correct SMHI forecast API URL."""
        assert "opendata-download-metfcst.smhi.se" in SMHI_FORECAST_API_BASE
        assert SMHI_FORECAST_API_BASE.startswith("https://")

    def test_api_url_format(self):
        """API URL should be properly formatted."""
        assert SMHI_FORECAST_API_BASE.endswith("/api")


class TestForecastParametersConfig:
    """Tests for forecast parameters configuration."""

    def test_has_temperature(self):
        """Parameters should include temperature."""
        assert "t" in FORECAST_PARAMETERS
        assert FORECAST_PARAMETERS["t"] == "temperature"

    def test_has_wind_speed(self):
        """Parameters should include wind speed."""
        assert "ws" in FORECAST_PARAMETERS
        assert FORECAST_PARAMETERS["ws"] == "wind_speed"

    def test_has_precipitation(self):
        """Parameters should include precipitation."""
        assert "pcat" in FORECAST_PARAMETERS or "pmean" in FORECAST_PARAMETERS

    def test_parameter_names_are_strings(self):
        """Parameter names should be strings."""
        for param_name in FORECAST_PARAMETERS.values():
            assert isinstance(param_name, str)

    def test_parameter_keys_are_strings(self):
        """Parameter keys should be strings."""
        for param_key in FORECAST_PARAMETERS.keys():
            assert isinstance(param_key, str)


class TestForecastLocationsConfig:
    """Tests for forecast locations configuration."""

    def test_has_locations(self):
        """Config should have forecast locations defined."""
        assert len(FORECAST_LOCATIONS) > 0

    def test_location_structure(self):
        """Each location should have name, lat, lon, and lakes."""
        for location_id, location_info in FORECAST_LOCATIONS.items():
            assert isinstance(location_id, str)
            assert "name" in location_info
            assert "lat" in location_info
            assert "lon" in location_info
            assert "lakes" in location_info
            assert isinstance(location_info["name"], str)
            assert isinstance(location_info["lat"], (int, float))
            assert isinstance(location_info["lon"], (int, float))
            assert isinstance(location_info["lakes"], list)

    def test_covers_major_lakes(self):
        """Locations should cover major Swedish lakes."""
        all_lakes = set()
        for location_info in FORECAST_LOCATIONS.values():
            all_lakes.update(location_info["lakes"])

        # Check for Mälaren coverage
        assert "malaren" in all_lakes, "Missing coverage for malaren"

    def test_location_names_not_empty(self):
        """Location names should not be empty."""
        for location_info in FORECAST_LOCATIONS.values():
            assert len(location_info["name"]) > 0

    def test_lakes_not_empty(self):
        """Each location should cover at least one lake."""
        for location_info in FORECAST_LOCATIONS.values():
            assert len(location_info["lakes"]) > 0

    def test_coordinates_valid(self):
        """Coordinates should be valid for Sweden."""
        for location_info in FORECAST_LOCATIONS.values():
            # Sweden latitude range: ~55-70 N
            assert 55.0 <= location_info["lat"] <= 70.0
            # Sweden longitude range: ~10-25 E
            assert 10.0 <= location_info["lon"] <= 25.0


class TestPathsConfig:
    """Tests for path configuration."""

    def test_data_dir_is_path(self):
        """DATA_DIR should be a Path object."""
        assert isinstance(DATA_DIR, Path)

    def test_log_dir_is_path(self):
        """LOG_DIR should be a Path object."""
        assert isinstance(LOG_DIR, Path)

    def test_log_file_is_path(self):
        """LOG_FILE should be a Path object."""
        assert isinstance(LOG_FILE, Path)

    def test_log_file_in_log_dir(self):
        """LOG_FILE should be inside LOG_DIR."""
        assert LOG_FILE.parent == LOG_DIR
