"""Tests for SMHI PMP (Point Meteorological Prognosis) API client."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import responses

import sys
sys.path.insert(0, str(__file__).replace("/tests/test_smhi_forecast_client.py", "/src"))

from smhi_forecast_client import SMHIForecastClient, SMHIForecastClientError


class TestSMHIForecastClient:
    """Tests for SMHIForecastClient class."""

    @pytest.fixture
    def client(self):
        """Create a client instance for testing."""
        return SMHIForecastClient(timeout=10)

    def test_init_defaults(self):
        """Client should initialize with default values."""
        client = SMHIForecastClient()
        assert client.timeout == 30
        assert client.session is not None

    def test_init_custom_timeout(self):
        """Client should accept custom timeout."""
        client = SMHIForecastClient(timeout=60)
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
    def test_get_forecast(self, client):
        """get_forecast should return forecast data."""
        lat, lon = 59.33, 18.07

        responses.add(
            responses.GET,
            f"{client.base_url}/category/pmp3g/version/2/geotype/point/lon/{lon}/lat/{lat}/data.json",
            json={
                "approvedTime": "2024-01-15T12:00:00Z",
                "referenceTime": "2024-01-15T12:00:00Z",
                "geometry": {
                    "type": "Point",
                    "coordinates": [[lon, lat]]
                },
                "timeSeries": [
                    {
                        "validTime": "2024-01-15T13:00:00Z",
                        "parameters": [
                            {"name": "t", "values": [-5.2]},
                            {"name": "ws", "values": [3.5]},
                        ]
                    }
                ]
            },
            status=200,
        )

        forecast_data = client.get_forecast(lat=lat, lon=lon)

        assert "timeSeries" in forecast_data
        assert len(forecast_data["timeSeries"]) == 1
        assert forecast_data["approvedTime"] == "2024-01-15T12:00:00Z"

    @responses.activate
    def test_get_forecast_error(self, client):
        """get_forecast should raise error on API failure."""
        lat, lon = 59.33, 18.07

        responses.add(
            responses.GET,
            f"{client.base_url}/category/pmp3g/version/2/geotype/point/lon/{lon}/lat/{lat}/data.json",
            json={"error": "Invalid coordinates"},
            status=400,
        )

        with pytest.raises(SMHIForecastClientError):
            client.get_forecast(lat=lat, lon=lon)

    def test_parse_forecast(self, client):
        """parse_forecast should extract forecast entries."""
        forecast_data = {
            "timeSeries": [
                {
                    "validTime": "2024-01-15T13:00:00Z",
                    "parameters": [
                        {"name": "t", "values": [-5.2]},
                        {"name": "ws", "values": [3.5]},
                        {"name": "pcat", "values": [0]},
                    ]
                },
                {
                    "validTime": "2024-01-15T14:00:00Z",
                    "parameters": [
                        {"name": "t", "values": [-4.8]},
                        {"name": "ws", "values": [3.2]},
                    ]
                }
            ]
        }

        parsed = client.parse_forecast(forecast_data)

        assert len(parsed) == 2
        assert parsed[0]["timestamp"] == "2024-01-15T13:00:00+00:00"
        assert parsed[0]["parameters"]["temperature"] == -5.2
        assert parsed[0]["parameters"]["wind_speed"] == 3.5
        assert parsed[1]["timestamp"] == "2024-01-15T14:00:00+00:00"

    def test_parse_forecast_empty_timeseries(self, client):
        """parse_forecast should handle empty timeSeries."""
        forecast_data = {"timeSeries": []}

        parsed = client.parse_forecast(forecast_data)

        assert parsed == []

    def test_parse_forecast_missing_parameters(self, client):
        """parse_forecast should handle entries with missing parameters."""
        forecast_data = {
            "timeSeries": [
                {
                    "validTime": "2024-01-15T13:00:00Z",
                    "parameters": [
                        {"name": "t", "values": [-5.2]},
                    ]
                },
                {
                    "validTime": "2024-01-15T14:00:00Z",
                    "parameters": []
                }
            ]
        }

        parsed = client.parse_forecast(forecast_data)

        assert len(parsed) == 2
        assert "temperature" in parsed[0]["parameters"]
        assert len(parsed[1]["parameters"]) == 0

    def test_parse_forecast_unknown_parameter(self, client):
        """parse_forecast should ignore unknown parameters."""
        forecast_data = {
            "timeSeries": [
                {
                    "validTime": "2024-01-15T13:00:00Z",
                    "parameters": [
                        {"name": "t", "values": [-5.2]},
                        {"name": "unknown_param", "values": [99]},
                    ]
                }
            ]
        }

        parsed = client.parse_forecast(forecast_data)

        assert len(parsed) == 1
        assert "temperature" in parsed[0]["parameters"]
        assert "unknown_param" not in parsed[0]["parameters"]

    @responses.activate
    def test_get_parsed_forecast(self, client):
        """get_parsed_forecast should fetch and parse in one call."""
        lat, lon = 59.33, 18.07

        responses.add(
            responses.GET,
            f"{client.base_url}/category/pmp3g/version/2/geotype/point/lon/{lon}/lat/{lat}/data.json",
            json={
                "approvedTime": "2024-01-15T12:00:00Z",
                "timeSeries": [
                    {
                        "validTime": "2024-01-15T13:00:00Z",
                        "parameters": [
                            {"name": "t", "values": [-5.2]},
                        ]
                    }
                ]
            },
            status=200,
        )

        parsed = client.get_parsed_forecast(lat=lat, lon=lon)

        assert len(parsed) == 1
        assert parsed[0]["parameters"]["temperature"] == -5.2

    def test_get_forecast_metadata(self, client):
        """get_forecast_metadata should extract metadata."""
        forecast_data = {
            "approvedTime": "2024-01-15T12:00:00Z",
            "referenceTime": "2024-01-15T11:00:00Z",
            "geometry": {
                "type": "Point",
                "coordinates": [[18.07, 59.33]]
            },
            "timeSeries": []
        }

        metadata = client.get_forecast_metadata(forecast_data)

        assert metadata["approved_time"] == "2024-01-15T12:00:00Z"
        assert metadata["reference_time"] == "2024-01-15T11:00:00Z"
        assert metadata["geometry_type"] == "Point"
        assert metadata["coordinates"] == [[18.07, 59.33]]

    def test_get_forecast_metadata_missing_fields(self, client):
        """get_forecast_metadata should handle missing fields."""
        forecast_data = {}

        metadata = client.get_forecast_metadata(forecast_data)

        assert metadata["approved_time"] is None
        assert metadata["reference_time"] is None
        assert metadata["geometry_type"] is None
        assert metadata["coordinates"] == []


class TestSMHIForecastClientError:
    """Tests for SMHIForecastClientError exception."""

    def test_error_message(self):
        """SMHIForecastClientError should preserve message."""
        error = SMHIForecastClientError("Connection failed")
        assert str(error) == "Connection failed"

    @responses.activate
    def test_get_raises_on_network_error(self):
        """_get should raise SMHIForecastClientError on network failure."""
        import requests as req

        client = SMHIForecastClient()

        responses.add(
            responses.GET,
            f"{client.base_url}/test",
            body=req.exceptions.ConnectionError("Network error"),
        )

        with pytest.raises(SMHIForecastClientError):
            client._get(f"{client.base_url}/test")


class TestSMHIForecastClientIntegration:
    """Integration tests requiring real API access.

    These tests are marked with 'integration' and skipped by default.
    Run with: pytest -m integration
    """

    @pytest.fixture
    def real_client(self):
        """Create a client for real API testing."""
        return SMHIForecastClient()

    @pytest.mark.integration
    def test_real_get_forecast(self, real_client):
        """Test fetching forecast from real SMHI API."""
        # Stockholm coordinates
        forecast_data = real_client.get_forecast(lat=59.33, lon=18.07)

        assert isinstance(forecast_data, dict)
        assert "timeSeries" in forecast_data
        assert len(forecast_data["timeSeries"]) > 0

    @pytest.mark.integration
    def test_real_parse_forecast(self, real_client):
        """Test parsing real forecast data."""
        forecast_data = real_client.get_forecast(lat=59.33, lon=18.07)
        parsed = real_client.parse_forecast(forecast_data)

        assert isinstance(parsed, list)
        assert len(parsed) > 0
        assert "timestamp" in parsed[0]
        assert "parameters" in parsed[0]
