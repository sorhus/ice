"""SMHI Open Data API client for fetching weather observations."""

import logging
from datetime import datetime, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import SMHI_API_BASE, PARAMETERS

logger = logging.getLogger(__name__)


class SMHIClientError(Exception):
    """Exception raised for SMHI API errors."""
    pass


class SMHIClient:
    """Client for SMHI Open Data Meteorological Observations API.

    API documentation: https://opendata.smhi.se/apidocs/metobs/index.html
    """

    def __init__(self, timeout: int = 30):
        """Initialize the SMHI client.

        Args:
            timeout: Request timeout in seconds.
        """
        self.base_url = SMHI_API_BASE
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers
        session.headers.update({
            "Accept": "application/json",
            "User-Agent": "NordicIce-WeatherCollector/1.0",
        })

        return session

    def _get(self, url: str) -> dict[str, Any]:
        """Make a GET request to the API.

        Args:
            url: Full URL to request.

        Returns:
            JSON response as dictionary.

        Raises:
            SMHIClientError: If the request fails.
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {url} - {e}")
            raise SMHIClientError(f"Failed to fetch data from SMHI: {e}") from e

    def get_stations(self, parameter_id: int) -> list[dict[str, Any]]:
        """Get all stations that have data for a given parameter.

        Args:
            parameter_id: The SMHI parameter ID (e.g., 1 for temperature).

        Returns:
            List of station metadata dictionaries.
        """
        url = f"{self.base_url}/version/1.0/parameter/{parameter_id}.json"
        data = self._get(url)
        return data.get("station", [])

    def get_latest_observations(
        self,
        station_id: int,
        parameter_id: int,
    ) -> list[dict[str, Any]]:
        """Get the latest observations for a station and parameter.

        Uses the 'latest-day' period which contains the most recent data.

        Args:
            station_id: The weather station ID.
            parameter_id: The SMHI parameter ID.

        Returns:
            List of observation dictionaries with 'timestamp' and 'value' keys.
        """
        # Build URL for latest observations
        # Format: /version/1.0/parameter/{param}/station/{station}/period/latest-day/data.json
        url = (
            f"{self.base_url}/version/1.0/parameter/{parameter_id}"
            f"/station/{station_id}/period/latest-day/data.json"
        )

        try:
            data = self._get(url)
            observations = []

            for value_entry in data.get("value", []):
                # Convert timestamp (milliseconds since epoch) to datetime
                timestamp_ms = value_entry.get("date")
                if timestamp_ms is None:
                    continue

                dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
                value = value_entry.get("value")

                # Handle missing values (SMHI uses empty string for missing)
                if value == "" or value is None:
                    continue

                observations.append({
                    "timestamp": dt.isoformat(),
                    "value": float(value),
                    "quality": value_entry.get("quality", "unknown"),
                })

            return observations

        except SMHIClientError:
            logger.warning(
                f"Could not fetch observations for station {station_id}, "
                f"parameter {parameter_id}"
            )
            return []

    def get_observations_for_station(
        self,
        station_id: int,
    ) -> dict[str, list[dict[str, Any]]]:
        """Get all configured weather parameters for a station.

        Args:
            station_id: The weather station ID.

        Returns:
            Dictionary mapping parameter names to observation lists.
        """
        results = {}

        for param_id, param_name in PARAMETERS.items():
            logger.debug(
                f"Fetching {param_name} (param {param_id}) for station {station_id}"
            )
            observations = self.get_latest_observations(station_id, param_id)
            results[param_name] = observations

        return results

    def get_station_metadata(
        self,
        station_id: int,
        parameter_id: int = 1,
    ) -> dict[str, Any] | None:
        """Get metadata for a specific station.

        Args:
            station_id: The weather station ID.
            parameter_id: Parameter ID to use for metadata lookup.

        Returns:
            Station metadata dictionary or None if not found.
        """
        stations = self.get_stations(parameter_id)

        for station in stations:
            if station.get("id") == station_id:
                return {
                    "id": station.get("id"),
                    "name": station.get("name"),
                    "latitude": station.get("latitude"),
                    "longitude": station.get("longitude"),
                    "height": station.get("height"),
                    "active": station.get("active", False),
                }

        return None
