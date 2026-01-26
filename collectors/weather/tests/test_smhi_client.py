"""Tests for SMHI Open Data API client."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import responses

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_smhi_client.py", "/src"))

from smhi_client import SMHIClient, SMHIClientError


class TestSMHIClient:
    """Tests for SMHIClient class."""

    @pytest.fixture
    def client(self):
        """Create a client instance for testing."""
        return SMHIClient(timeout=10)

    def test_init_defaults(self):
        """Client should initialize with default values."""
        client = SMHIClient()
        assert client.timeout == 30
        assert client.session is not None

    def test_init_custom_timeout(self):
        """Client should accept custom timeout."""
        client = SMHIClient(timeout=60)
        assert client.timeout == 60

    def test_session_has_retry_logic(self, client):
        """Session should have retry adapter configured."""
        adapter = client.session.get_adapter("https://")
        assert adapter is not None
        assert adapter.max_retries.total == 3

    def test_session_has_user_agent(self, client):
        """Session should have User-Agent header."""
        assert "User-Agent" in client.session.headers
        assert "NordicIce" in client.session.headers["User-Agent"]

    @responses.activate
    def test_get_stations(self, client):
        """get_stations should return list of stations."""
        responses.add(
            responses.GET,
            f"{client.base_url}/version/1.0/parameter/1.json",
            json={
                "station": [
                    {"id": 97100, "name": "Stockholm-Arlanda"},
                    {"id": 98210, "name": "Stockholm"},
                ]
            },
            status=200,
        )

        stations = client.get_stations(parameter_id=1)

        assert len(stations) == 2
        assert stations[0]["id"] == 97100
        assert stations[1]["name"] == "Stockholm"

    @responses.activate
    def test_get_stations_empty(self, client):
        """get_stations should return empty list when no stations."""
        responses.add(
            responses.GET,
            f"{client.base_url}/version/1.0/parameter/1.json",
            json={"station": []},
            status=200,
        )

        stations = client.get_stations(parameter_id=1)

        assert stations == []

    @responses.activate
    def test_get_latest_observations(self, client):
        """get_latest_observations should parse observations correctly."""
        # Create timestamp for 2024-01-15 10:00:00 UTC
        timestamp_ms = int(datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

        responses.add(
            responses.GET,
            f"{client.base_url}/version/1.0/parameter/1/station/97100/period/latest-day/data.json",
            json={
                "value": [
                    {"date": timestamp_ms, "value": "-5.2", "quality": "G"},
                    {"date": timestamp_ms + 3600000, "value": "-4.8", "quality": "G"},
                ]
            },
            status=200,
        )

        observations = client.get_latest_observations(station_id=97100, parameter_id=1)

        assert len(observations) == 2
        assert observations[0]["value"] == pytest.approx(-5.2)
        assert observations[1]["value"] == pytest.approx(-4.8)
        assert "timestamp" in observations[0]
        assert observations[0]["quality"] == "G"

    @responses.activate
    def test_get_latest_observations_filters_missing_values(self, client):
        """get_latest_observations should filter out missing values."""
        timestamp_ms = int(datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

        responses.add(
            responses.GET,
            f"{client.base_url}/version/1.0/parameter/1/station/97100/period/latest-day/data.json",
            json={
                "value": [
                    {"date": timestamp_ms, "value": "-5.2", "quality": "G"},
                    {"date": timestamp_ms + 3600000, "value": "", "quality": "G"},  # Missing
                    {"date": timestamp_ms + 7200000, "value": None, "quality": "G"},  # Missing
                    {"date": timestamp_ms + 10800000, "value": "-3.0", "quality": "G"},
                ]
            },
            status=200,
        )

        observations = client.get_latest_observations(station_id=97100, parameter_id=1)

        assert len(observations) == 2
        assert observations[0]["value"] == pytest.approx(-5.2)
        assert observations[1]["value"] == pytest.approx(-3.0)

    @responses.activate
    def test_get_latest_observations_handles_error(self, client):
        """get_latest_observations should return empty list on API error."""
        responses.add(
            responses.GET,
            f"{client.base_url}/version/1.0/parameter/1/station/99999/period/latest-day/data.json",
            json={"error": "Station not found"},
            status=404,
        )

        observations = client.get_latest_observations(station_id=99999, parameter_id=1)

        assert observations == []

    @responses.activate
    def test_get_observations_for_station(self, client):
        """get_observations_for_station should fetch all parameters."""
        timestamp_ms = int(datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

        # Mock responses for each parameter
        for param_id in [1, 4, 7, 16]:
            responses.add(
                responses.GET,
                f"{client.base_url}/version/1.0/parameter/{param_id}/station/97100/period/latest-day/data.json",
                json={
                    "value": [
                        {"date": timestamp_ms, "value": "10.5", "quality": "G"},
                    ]
                },
                status=200,
            )

        observations = client.get_observations_for_station(station_id=97100)

        assert "temperature" in observations
        assert "wind_speed" in observations
        assert "precipitation" in observations
        assert "cloud_cover" in observations
        assert len(observations["temperature"]) == 1

    @responses.activate
    def test_get_station_metadata(self, client):
        """get_station_metadata should return station info."""
        responses.add(
            responses.GET,
            f"{client.base_url}/version/1.0/parameter/1.json",
            json={
                "station": [
                    {
                        "id": 97100,
                        "name": "Stockholm-Arlanda",
                        "latitude": 59.6519,
                        "longitude": 17.9436,
                        "height": 61.0,
                        "active": True,
                    },
                    {"id": 98210, "name": "Stockholm"},
                ]
            },
            status=200,
        )

        metadata = client.get_station_metadata(station_id=97100)

        assert metadata is not None
        assert metadata["id"] == 97100
        assert metadata["name"] == "Stockholm-Arlanda"
        assert metadata["latitude"] == pytest.approx(59.65, abs=0.01)
        assert metadata["active"] is True

    @responses.activate
    def test_get_station_metadata_not_found(self, client):
        """get_station_metadata should return None for unknown station."""
        responses.add(
            responses.GET,
            f"{client.base_url}/version/1.0/parameter/1.json",
            json={"station": []},
            status=200,
        )

        metadata = client.get_station_metadata(station_id=99999)

        assert metadata is None


class TestSMHIClientError:
    """Tests for SMHIClientError exception."""

    def test_error_message(self):
        """SMHIClientError should preserve message."""
        error = SMHIClientError("Connection failed")
        assert str(error) == "Connection failed"

    @responses.activate
    def test_get_raises_on_network_error(self):
        """_get should raise SMHIClientError on network failure."""
        client = SMHIClient()

        responses.add(
            responses.GET,
            f"{client.base_url}/test",
            body=Exception("Network error"),
        )

        with pytest.raises(SMHIClientError):
            client._get(f"{client.base_url}/test")


class TestSMHIClientIntegration:
    """Integration tests requiring real API access.

    These tests are marked with 'integration' and skipped by default.
    Run with: pytest -m integration
    """

    @pytest.fixture
    def real_client(self):
        """Create a client for real API testing."""
        return SMHIClient()

    @pytest.mark.integration
    def test_real_get_stations(self, real_client):
        """Test fetching stations from real SMHI API."""
        stations = real_client.get_stations(parameter_id=1)

        assert isinstance(stations, list)
        assert len(stations) > 0

    @pytest.mark.integration
    def test_real_get_observations(self, real_client):
        """Test fetching observations from real SMHI API."""
        # Use a known active station
        observations = real_client.get_latest_observations(
            station_id=97100,  # Stockholm-Arlanda
            parameter_id=1,    # Temperature
        )

        assert isinstance(observations, list)
        # May be empty if no recent data, but should not raise
