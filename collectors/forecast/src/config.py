"""Configuration for the weather forecast collector."""

import os
from pathlib import Path

# SMHI PMP API base URL
SMHI_FORECAST_API_BASE = "https://opendata-download-metfcst.smhi.se/api"

# Data output directory
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))

# Forecast locations in Stockholm/Mälaren region
# Using coordinates near weather stations for consistency
# Format: location_id: {"name": str, "lat": float, "lon": float, "lakes": list}
FORECAST_LOCATIONS = {
    "stockholm_central": {
        "name": "Stockholm Central",
        "lat": 59.33,
        "lon": 18.07,
        "lakes": ["malaren"],
    },
    "uppsala": {
        "name": "Uppsala",
        "lat": 59.86,
        "lon": 17.64,
        "lakes": ["malaren", "ekoln"],
    },
    "enkoping": {
        "name": "Enköping",
        "lat": 59.64,
        "lon": 17.08,
        "lakes": ["malaren"],
    },
    "sodertalje": {
        "name": "Södertälje",
        "lat": 59.20,
        "lon": 17.63,
        "lakes": ["malaren"],
    },
}

# SMHI PMP parameters to extract
# See: https://opendata.smhi.se/apidocs/metfcst/parameters.html
FORECAST_PARAMETERS = {
    "t": "temperature",         # Air temperature (C)
    "ws": "wind_speed",         # Wind speed (m/s)
    "pcat": "precipitation_category",  # Precipitation category
    "pmean": "precipitation_mean",     # Mean precipitation (mm/h)
}

# Logging configuration
LOG_DIR = Path(os.getenv("LOG_DIR", "/logs"))
LOG_FILE = LOG_DIR / "forecast-collector.log"
