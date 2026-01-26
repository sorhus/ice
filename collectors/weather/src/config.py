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

# Weather stations near major Swedish lakes
# Selected stations cover the main skating regions
# Format: station_id: {"name": str, "lakes": list of nearby lakes}
STATIONS = {
    # Stockholm area / Mälaren
    97100: {"name": "Stockholm-Arlanda", "lakes": ["malaren"]},
    98210: {"name": "Stockholm", "lakes": ["malaren"]},

    # Vänern area
    72420: {"name": "Karlstad Flygplats", "lakes": ["vanern"]},
    72530: {"name": "Lidköping", "lakes": ["vanern"]},

    # Vättern area
    85090: {"name": "Jönköping", "lakes": ["vattern"]},
    84540: {"name": "Motala", "lakes": ["vattern"]},

    # Hjälmaren area
    96190: {"name": "Örebro Flygplats", "lakes": ["hjalmaren"]},

    # Siljan area (Dalarna)
    105260: {"name": "Mora", "lakes": ["siljan"]},

    # Storsjön area (Jämtland)
    123480: {"name": "Östersund-Frösön", "lakes": ["storsjon"]},

    # Norrbotten lakes
    162860: {"name": "Luleå-Kallax", "lakes": ["lulealven"]},

    # Uppsala area
    97510: {"name": "Uppsala Flygplats", "lakes": ["malaren", "ekoln"]},
}

# Reference temperature for cold degree day calculation (Celsius)
FREEZING_POINT = 0.0

# Logging configuration
LOG_DIR = Path(os.getenv("LOG_DIR", "/logs"))
LOG_FILE = LOG_DIR / "weather-collector.log"
