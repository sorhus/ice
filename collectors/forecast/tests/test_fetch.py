"""Tests for forecast fetch script."""

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
    parse_args,
    save_forecast_data,
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


class TestSaveForecastData:
    """Tests for save_forecast_data function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def sample_forecasts(self):
        """Sample forecast data."""
        return [
            {
                "timestamp": "2024-01-15T13:00:00+00:00",
                "valid_time": "2024-01-15T13:00:00Z",
                "parameters": {
                    "temperature": -5.2,
                    "wind_speed": 3.5,
                }
            },
            {
                "timestamp": "2024-01-15T14:00:00+00:00",
                "valid_time": "2024-01-15T14:00:00Z",
                "parameters": {
                    "temperature": -4.8,
                    "wind_speed": 3.2,
                }
            }
        ]

    @pytest.fixture
    def sample_metadata(self):
        """Sample forecast metadata."""
        return {
            "approved_time": "2024-01-15T12:00:00Z",
            "reference_time": "2024-01-15T12:00:00Z",
            "geometry_type": "Point",
            "coordinates": [[18.07, 59.33]],
        }

    def test_saves_json_file(self, mock_logger, sample_forecasts, sample_metadata):
        """save_forecast_data should create JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                save_forecast_data(
                    location_id="stockholm_central",
                    location_info={
                        "name": "Stockholm Central",
                        "lat": 59.33,
                        "lon": 18.07,
                        "lakes": ["malaren"]
                    },
                    forecasts=sample_forecasts,
                    metadata=sample_metadata,
                    logger=mock_logger,
                    dry_run=False,
                )

                # Check that timestamp directory was created
                now = datetime.now(timezone.utc)
                timestamp = now.strftime("%Y-%m-%d-%H")
                timestamp_dir = Path(tmpdir) / timestamp
                assert timestamp_dir.exists()

                # Check that location file was created
                location_file = timestamp_dir / "location_stockholm_central.json"
                assert location_file.exists()

                # Verify JSON content
                with open(location_file) as f:
                    data = json.load(f)

                assert data["location_id"] == "stockholm_central"
                assert data["location_name"] == "Stockholm Central"
                assert data["latitude"] == 59.33
                assert data["longitude"] == 18.07
                assert data["lakes"] == ["malaren"]
                assert "forecasts" in data
                assert "metadata" in data
                assert data["forecast_count"] == 2

    def test_dry_run_skips_save(self, mock_logger, sample_forecasts, sample_metadata):
        """save_forecast_data should not create files in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                save_forecast_data(
                    location_id="stockholm_central",
                    location_info={
                        "name": "Stockholm Central",
                        "lat": 59.33,
                        "lon": 18.07,
                        "lakes": ["malaren"]
                    },
                    forecasts=sample_forecasts,
                    metadata=sample_metadata,
                    logger=mock_logger,
                    dry_run=True,
                )

                # Directory should NOT be created in dry-run mode
                now = datetime.now(timezone.utc)
                timestamp = now.strftime("%Y-%m-%d-%H")
                timestamp_dir = Path(tmpdir) / timestamp
                assert not timestamp_dir.exists()

                # Verify dry-run was logged
                mock_logger.info.assert_called()
                log_message = mock_logger.info.call_args[0][0]
                assert "[DRY-RUN]" in log_message

    def test_logs_on_save(self, mock_logger, sample_forecasts, sample_metadata):
        """save_forecast_data should log when saving."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                save_forecast_data(
                    location_id="stockholm_central",
                    location_info={
                        "name": "Stockholm Central",
                        "lat": 59.33,
                        "lon": 18.07,
                        "lakes": ["malaren"]
                    },
                    forecasts=sample_forecasts,
                    metadata=sample_metadata,
                    logger=mock_logger,
                    dry_run=False,
                )

                mock_logger.info.assert_called()

    def test_includes_forecast_count(self, mock_logger, sample_forecasts, sample_metadata):
        """save_forecast_data should include forecast count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                save_forecast_data(
                    location_id="stockholm_central",
                    location_info={
                        "name": "Stockholm Central",
                        "lat": 59.33,
                        "lon": 18.07,
                        "lakes": ["malaren"]
                    },
                    forecasts=sample_forecasts,
                    metadata=sample_metadata,
                    logger=mock_logger,
                    dry_run=False,
                )

                now = datetime.now(timezone.utc)
                timestamp = now.strftime("%Y-%m-%d-%H")
                location_file = Path(tmpdir) / timestamp / "location_stockholm_central.json"

                with open(location_file) as f:
                    data = json.load(f)

                assert data["forecast_count"] == len(sample_forecasts)


class TestFetchAllForecasts:
    """Tests for fetch_all_forecasts function."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()

    @pytest.fixture
    def mock_client(self):
        """Create a mock SMHIForecastClient."""
        with patch("fetch.SMHIForecastClient") as mock:
            client_instance = MagicMock()
            client_instance.get_forecast.return_value = {
                "approvedTime": "2024-01-15T12:00:00Z",
                "timeSeries": []
            }
            client_instance.parse_forecast.return_value = [
                {
                    "timestamp": "2024-01-15T13:00:00+00:00",
                    "parameters": {"temperature": -5.0}
                }
            ]
            client_instance.get_forecast_metadata.return_value = {
                "approved_time": "2024-01-15T12:00:00Z",
            }
            mock.return_value = client_instance
            yield client_instance

    def test_respects_limit(self, mock_logger, mock_client):
        """fetch_all_forecasts should respect limit option."""
        from fetch import fetch_all_forecasts

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                options = RunOptions(limit=2)
                stats = fetch_all_forecasts(mock_logger, options)

                # Should only fetch 2 locations regardless of how many are configured
                assert mock_client.get_forecast.call_count == 2

    def test_counts_success_and_failures(self, mock_logger, mock_client):
        """fetch_all_forecasts should count successes and failures."""
        from fetch import fetch_all_forecasts

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("fetch.DATA_DIR", Path(tmpdir)):
                options = RunOptions(limit=2)
                stats = fetch_all_forecasts(mock_logger, options)

                assert "success" in stats
                assert "failed" in stats
                assert stats["success"] + stats["failed"] == 2
