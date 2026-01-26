"""Tests for weather collector configuration."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_config.py", "/src"))

from config import (
    DATA_DIR,
    FREEZING_POINT,
    LOG_DIR,
    LOG_FILE,
    PARAMETERS,
    SMHI_API_BASE,
    STATIONS,
)


class TestSMHIConfig:
    """Tests for SMHI API configuration."""

    def test_api_base_url(self):
        """Config should have correct SMHI API URL."""
        assert "opendata-download-metobs.smhi.se" in SMHI_API_BASE
        assert SMHI_API_BASE.startswith("https://")

    def test_api_url_format(self):
        """API URL should be properly formatted."""
        assert SMHI_API_BASE.endswith("/api")


class TestParametersConfig:
    """Tests for weather parameters configuration."""

    def test_has_temperature(self):
        """Parameters should include temperature."""
        assert 1 in PARAMETERS
        assert PARAMETERS[1] == "temperature"

    def test_has_wind_speed(self):
        """Parameters should include wind speed."""
        assert 4 in PARAMETERS
        assert PARAMETERS[4] == "wind_speed"

    def test_has_precipitation(self):
        """Parameters should include precipitation."""
        assert 7 in PARAMETERS
        assert PARAMETERS[7] == "precipitation"

    def test_has_cloud_cover(self):
        """Parameters should include cloud cover."""
        assert 16 in PARAMETERS
        assert PARAMETERS[16] == "cloud_cover"

    def test_parameter_ids_are_ints(self):
        """Parameter IDs should be integers."""
        for param_id in PARAMETERS.keys():
            assert isinstance(param_id, int)

    def test_parameter_names_are_strings(self):
        """Parameter names should be strings."""
        for param_name in PARAMETERS.values():
            assert isinstance(param_name, str)


class TestStationsConfig:
    """Tests for weather stations configuration."""

    def test_has_stations(self):
        """Config should have weather stations defined."""
        assert len(STATIONS) > 0

    def test_station_structure(self):
        """Each station should have name and lakes."""
        for station_id, station_info in STATIONS.items():
            assert isinstance(station_id, int)
            assert "name" in station_info
            assert "lakes" in station_info
            assert isinstance(station_info["name"], str)
            assert isinstance(station_info["lakes"], list)

    def test_covers_major_lakes(self):
        """Stations should cover major Swedish lakes."""
        all_lakes = set()
        for station_info in STATIONS.values():
            all_lakes.update(station_info["lakes"])

        # Check for major lakes
        major_lakes = {"malaren", "vanern", "vattern"}
        for lake in major_lakes:
            assert lake in all_lakes, f"Missing coverage for {lake}"

    def test_station_names_not_empty(self):
        """Station names should not be empty."""
        for station_info in STATIONS.values():
            assert len(station_info["name"]) > 0

    def test_lakes_not_empty(self):
        """Each station should cover at least one lake."""
        for station_info in STATIONS.values():
            assert len(station_info["lakes"]) > 0


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


class TestFreezingPoint:
    """Tests for freezing point configuration."""

    def test_freezing_point_value(self):
        """Freezing point should be 0.0 Celsius."""
        assert FREEZING_POINT == 0.0

    def test_freezing_point_type(self):
        """Freezing point should be a float."""
        assert isinstance(FREEZING_POINT, float)
