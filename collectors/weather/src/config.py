"""Configuration for the weather data collector."""

import os
from pathlib import Path

# SMHI Open Data API base URL
SMHI_API_BASE = "https://opendata-download-metobs.smhi.se/api"

# Data output directory
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))

# Weather parameters to collect
# See: https://opendata.smhi.se/apidocs/metobs/parameter.html
PARAMETERS = {
    1: "temperature",       # Air temperature (instantaneous, 1 hour)
    4: "wind_speed",        # Wind speed (average, 1 hour)
    7: "precipitation",     # Precipitation (sum, 1 hour)
    16: "cloud_cover",      # Total cloud cover (instantaneous, 1 hour)
}

# Weather stations in Stockholm/Mälaren region
# Only active stations from SMHI API (verified 2026-01)
# Format: station_id: {"name": str, "lakes": list of nearby lakes}
STATIONS = {
    # Mälaren - west
    97280: {"name": "Adelsö A", "lakes": ["malaren"]},  # Island in Mälaren
    97370: {"name": "Enköping", "lakes": ["malaren"]},

    # Mälaren - central/Stockholm
    97200: {"name": "Stockholm-Bromma Flygplats", "lakes": ["malaren"]},
    98230: {"name": "Stockholm-Observatoriekullen A", "lakes": ["malaren"]},
    97100: {"name": "Tullinge A", "lakes": ["malaren"]},

    # Mälaren - south
    97120: {"name": "Södertälje", "lakes": ["malaren"]},

    # Mälaren - north/Uppsala
    97400: {"name": "Stockholm-Arlanda Flygplats", "lakes": ["malaren", "ekoln"]},
    97510: {"name": "Uppsala Aut", "lakes": ["malaren", "ekoln"]},
    97530: {"name": "Uppsala Flygplats", "lakes": ["ekoln"]},

    # Outer Stockholm (reference)
    98040: {"name": "Berga", "lakes": ["malaren"]},
}

# Reference temperature for cold degree day calculation (Celsius)
FREEZING_POINT = 0.0

# Logging configuration
LOG_DIR = Path(os.getenv("LOG_DIR", "/logs"))
LOG_FILE = LOG_DIR / "weather-collector.log"
