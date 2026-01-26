"""Tests for weather fetch script."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_fetch.py", "/src"))

from fetch import (
    RunOptions,
    calculate_cold_degree_days,
    parse_args,
    save_station_data,
)


class TestRunOptions:
    """Tests for RunOptions dataclass."""

    def test_default_values(self):
        """RunOptions should have correct defaults."""
        options = RunOptions()

        assert options.dry_run is False
        assert options.limit is None
        assert options.verbose is False

    def test_custom_values(self):
        """RunOptions should accept custom values."""
        options = RunOptions(dry_run=True, limit=3, verbose=True)

        assert options.dry_run is True
        assert options.limit == 3
        assert options.verbose is True


class TestParseArgs:
    """Tests for argument parsing."""

    def test_parse_default_args(self):
        """Parsing no arguments should return defaults."""
        with patch("sys.argv", ["fetch.py"]):
            options = parse_args()

            assert options.dry_run is False
            assert options.limit is None
            assert options.verbose is False

    def test_parse_dry_run(self):
        """Parsing --dry-run should set dry_run flag."""
        with patch("sys.argv", ["fetch.py", "--dry-run"]):
            options = parse_args()

            assert options.dry_run is True

    def test_parse_limit(self):
        """Parsing --limit should set limit value."""
        with patch("sys.argv", ["fetch.py", "--limit", "3"]):
            options = parse_args()

            assert options.limit == 3

    def test_parse_verbose(self):
        """Parsing --verbose should set verbose flag."""
        with patch("sys.argv", ["fetch.py", "--verbose"]):
            options = parse_args()

            assert options.verbose is True

    def test_parse_verbose_short(self):
        """Parsing -v should set verbose flag."""
        with patch("sys.argv", ["fetch.py", "-v"]):
            options = parse_args()

            assert options.verbose is True

    def test_parse_all_args(self):
        """Parsing all arguments together."""
        with patch("sys.argv", ["fetch.py", "--dry-run", "--limit", "2", "-v"]):
            options = parse_args()

            assert options.dry_run is True
            assert options.limit == 2
            assert options.verbose is True


class TestCalculateColdDegreeDays:
    """Tests for cold degree day calculation."""

    def test_below_freezing(self):
        """CDD should be positive when average temp is below freezing."""
        observations = [
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": -5.0},
            {"timestamp": "2024-01-15T11:00:00+00:00", "value": -3.0},
            {"timestamp": "2024-01-15T12:00:00+00:00", "value": -4.0},
        ]

        cdd = calculate_cold_degree_days(observations)

        assert "2024-01-15" in cdd
        # Average is -4.0, so CDD = 0 - (-4.0) = 4.0
        assert cdd["2024-01-15"] == pytest.approx(4.0)

    def test_above_freezing(self):
        """CDD should be zero when average temp is above freezing."""
        observations = [
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": 5.0},
            {"timestamp": "2024-01-15T11:00:00+00:00", "value": 3.0},
            {"timestamp": "2024-01-15T12:00:00+00:00", "value": 4.0},
        ]

        cdd = calculate_cold_degree_days(observations)

        assert "2024-01-15" in cdd
        assert cdd["2024-01-15"] == 0.0

    def test_exactly_freezing(self):
        """CDD should be zero when average temp is exactly at freezing."""
        observations = [
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": 0.0},
            {"timestamp": "2024-01-15T11:00:00+00:00", "value": 0.0},
        ]

        cdd = calculate_cold_degree_days(observations)

        assert "2024-01-15" in cdd
        assert cdd["2024-01-15"] == 0.0

    def test_multiple_days(self):
        """CDD should calculate separately for each day."""
        observations = [
            # Day 1: average -5.0
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": -5.0},
            {"timestamp": "2024-01-15T11:00:00+00:00", "value": -5.0},
            # Day 2: average 2.0
            {"timestamp": "2024-01-16T10:00:00+00:00", "value": 2.0},
            {"timestamp": "2024-01-16T11:00:00+00:00", "value": 2.0},
        ]

        cdd = calculate_cold_degree_days(observations)

        assert cdd["2024-01-15"] == pytest.approx(5.0)
        assert cdd["2024-01-16"] == 0.0

    def test_empty_observations(self):
        """CDD should return empty dict for no observations."""
        cdd = calculate_cold_degree_days([])

        assert cdd == {}

    def test_single_observation(self):
        """CDD should handle single observation."""
        observations = [
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": -10.0},
        ]

        cdd = calculate_cold_degree_days(observations)

        assert cdd["2024-01-15"] == pytest.approx(10.0)

    def test_mixed_positive_negative(self):
        """CDD should handle mix of positive and negative temps."""
        observations = [
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": -2.0},
            {"timestamp": "2024-01-15T11:00:00+00:00", "value": 4.0},
            {"timestamp": "2024-01-15T12:00:00+00:00", "value": 1.0},
        ]

        cdd = calculate_cold_degree_days(observations)

        # Average is 1.0, above freezing
        assert cdd["2024-01-15"] == 0.0

    def test_rounding(self):
        """CDD should be rounded to 2 decimal places."""
        observations = [
            {"timestamp": "2024-01-15T10:00:00+00:00", "value": -3.333},
            {"timestamp": "2024-01-15T11:00:00+00:00", "value": -3.333},
            {"timestamp": "2024-01-15T12:00:00+00:00", "value": -3.334},
        ]

        cdd = calculate_cold_degree_days(observations)

        # Should be rounded to 2 decimal places
        assert cdd["2024-01-15"] == pytest.approx(3.33, abs=0.01)


class TestSaveStationData:
    """Tests for save_station_data function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def sample_observations(self):
        """Sample observations data."""
        return {
            "temperature": [
                {"timestamp": "2024-01-15T10:00:00+00:00", "value": -5.0},
                {"timestamp": "2024-01-15T11:00:00+00:00", "value": -4.0},
            ],
            "wind_speed": [
                {"timestamp": "2024-01-15T10:00:00+00:00", "value": 3.5},
            ],
        }

    @pytest.fixture
    def sample_cdd(self):
        """Sample cold degree days."""
        return {"2024-01-15": 4.5}

    def test_saves_json_file(self, mock_logger, sample_observations, sample_cdd):
        """save_station_data should create JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                save_station_data(
                    station_id=97100,
                    station_info={"name": "Stockholm-Arlanda", "lakes": ["malaren"]},
                    observations=sample_observations,
                    cold_degree_days=sample_cdd,
                    logger=mock_logger,
                    dry_run=False,
                )

                # Check that date directory was created
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                date_dir = Path(tmpdir) / today
                assert date_dir.exists()

                # Check that station file was created
                station_file = date_dir / "station_97100.json"
                assert station_file.exists()

                # Verify JSON content
                with open(station_file) as f:
                    data = json.load(f)

                assert data["station_id"] == 97100
                assert data["station_name"] == "Stockholm-Arlanda"
                assert data["lakes"] == ["malaren"]
                assert "observations" in data
                assert "cold_degree_days" in data

    def test_dry_run_skips_save(self, mock_logger, sample_observations, sample_cdd):
        """save_station_data should not create files in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                save_station_data(
                    station_id=97100,
                    station_info={"name": "Stockholm-Arlanda", "lakes": ["malaren"]},
                    observations=sample_observations,
                    cold_degree_days=sample_cdd,
                    logger=mock_logger,
                    dry_run=True,
                )

                # Directory should NOT be created in dry-run mode
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                date_dir = Path(tmpdir) / today
                assert not date_dir.exists()

                # Verify dry-run was logged
                mock_logger.info.assert_called()
                log_message = mock_logger.info.call_args[0][0]
                assert "[DRY-RUN]" in log_message

    def test_logs_on_save(self, mock_logger, sample_observations, sample_cdd):
        """save_station_data should log when saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                save_station_data(
                    station_id=97100,
                    station_info={"name": "Stockholm-Arlanda", "lakes": ["malaren"]},
                    observations=sample_observations,
                    cold_degree_days=sample_cdd,
                    logger=mock_logger,
                    dry_run=False,
                )

                mock_logger.info.assert_called()


class TestFetchAllStations:
    """Tests for fetch_all_stations function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_client(self):
        """Create a mock SMHIClient."""
        with patch("fetch.SMHIClient") as mock:
            client_instance = MagicMock()
            client_instance.get_observations_for_station.return_value = {
                "temperature": [
                    {"timestamp": "2024-01-15T10:00:00+00:00", "value": -5.0},
                ],
                "wind_speed": [],
                "precipitation": [],
                "cloud_cover": [],
            }
            mock.return_value = client_instance
            yield client_instance

    def test_respects_limit(self, mock_logger, mock_client):
        """fetch_all_stations should respect limit option."""
        from fetch import fetch_all_stations, STATIONS

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                options = RunOptions(limit=2)
                stats = fetch_all_stations(mock_logger, options)

                # Should only fetch 2 stations regardless of how many are configured
                assert mock_client.get_observations_for_station.call_count == 2

    def test_counts_success_and_failures(self, mock_logger, mock_client):
        """fetch_all_stations should count successes and failures."""
        from fetch import fetch_all_stations

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                options = RunOptions(limit=2)
                stats = fetch_all_stations(mock_logger, options)

                assert "success" in stats
                assert "failed" in stats
                assert stats["success"] + stats["failed"] == 2
