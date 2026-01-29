"""SMHI PMP (Point Meteorological Prognosis) API client for weather forecasts."""

import logging
from datetime import datetime, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import SMHI_FORECAST_API_BASE, FORECAST_PARAMETERS

logger = logging.getLogger(__name__)


class SMHIForecastClientError(Exception):
    """Exception raised for SMHI forecast API errors."""
    pass


class SMHIForecastClient:
    """Client for SMHI PMP (Point Meteorological Prognosis) API.

    API documentation: https://opendata.smhi.se/apidocs/metfcst/index.html
    """

    def __init__(self, timeout: int = 30):
        """Initialize the SMHI forecast client.

        Args:
            timeout: Request timeout in seconds.
        """
        self.base_url = SMHI_FORECAST_API_BASE
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
            "User-Agent": "NordicIce-ForecastCollector/1.0",
        })

        return session

    def _get(self, url: str) -> dict[str, Any]:
        """Make a GET request to the API.

        Args:
            url: Full URL to request.

        Returns:
            JSON response as dictionary.

        Raises:
            SMHIForecastClientError: If the request fails.
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f"API request failed: {url} - {e}")
            raise SMHIForecastClientError(f"Failed to fetch forecast from SMHI: {e}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {url} - {e}")
            raise SMHIForecastClientError(f"Failed to fetch forecast from SMHI: {e}") from e

    def get_forecast(self, lat: float, lon: float) -> dict[str, Any]:
        """Get weather forecast for a specific location.

        Args:
            lat: Latitude (decimal degrees).
            lon: Longitude (decimal degrees).

        Returns:
            Dictionary containing forecast data with timeSeries and metadata.

        Raises:
            SMHIForecastClientError: If the request fails.
        """
        # Build URL for PMP API
        # Format: /category/pmp3g/version/2/geotype/point/lon/{lon}/lat/{lat}/data.json
        url = (
            f"{self.base_url}/category/pmp3g/version/2"
            f"/geotype/point/lon/{lon}/lat/{lat}/data.json"
        )

        logger.debug(f"Fetching forecast for lat={lat}, lon={lon}")

        try:
            data = self._get(url)
            return data
        except SMHIForecastClientError:
            logger.warning(f"Could not fetch forecast for lat={lat}, lon={lon}")
            raise

    def parse_forecast(self, forecast_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse forecast data into structured format.

        Args:
            forecast_data: Raw forecast data from API.

        Returns:
            List of forecast entries with timestamp and parameter values.
        """
        time_series = forecast_data.get("timeSeries", [])
        parsed_forecasts = []

        for entry in time_series:
            # Parse timestamp
            valid_time = entry.get("validTime")
            if not valid_time:
                continue

            # Convert to datetime
            dt = datetime.fromisoformat(valid_time.replace("Z", "+00:00"))

            # Extract parameters
            parameters = {}
            for param_entry in entry.get("parameters", []):
                param_name = param_entry.get("name")
                param_values = param_entry.get("values", [])

                # Map to friendly names
                if param_name in FORECAST_PARAMETERS:
                    friendly_name = FORECAST_PARAMETERS[param_name]
                    # Most parameters have single value, take first
                    if param_values:
                        parameters[friendly_name] = param_values[0]

            # Create forecast entry
            forecast_entry = {
                "timestamp": dt.isoformat(),
                "valid_time": valid_time,
                "parameters": parameters,
            }

            parsed_forecasts.append(forecast_entry)

        return parsed_forecasts

    def get_parsed_forecast(self, lat: float, lon: float) -> list[dict[str, Any]]:
        """Get and parse weather forecast for a location.

        Args:
            lat: Latitude (decimal degrees).
            lon: Longitude (decimal degrees).

        Returns:
            List of parsed forecast entries.

        Raises:
            SMHIForecastClientError: If the request fails.
        """
        forecast_data = self.get_forecast(lat, lon)
        return self.parse_forecast(forecast_data)

    def get_forecast_metadata(self, forecast_data: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from forecast response.

        Args:
            forecast_data: Raw forecast data from API.

        Returns:
            Dictionary with metadata (approved_time, reference_time, etc.).
        """
        return {
            "approved_time": forecast_data.get("approvedTime"),
            "reference_time": forecast_data.get("referenceTime"),
            "geometry_type": forecast_data.get("geometry", {}).get("type"),
            "coordinates": forecast_data.get("geometry", {}).get("coordinates", []),
        }
