# Nordic Ice Skating Prediction System

## Overview

A multi-component system that collects and analyzes data to predict where ice conditions are suitable for Nordic skating in Sweden. The system combines satellite radar imagery, weather data, forecasts, and community observations.

## Goal

Predict/analyze ice conditions on lakes and waterways to help skaters find safe, skateable ice.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Data Collection Layer                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ SAR Imagery  │ │ Weather Data │ │ Forecasts    │ │ Observations       │  │
│  │ (Sentinel-1) │ │ (SMHI)       │ │ (SMHI)       │ │ (Skridskonet etc.) │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────────┬──────────┘  │
│         │                │                │                   │             │
└─────────┼────────────────┼────────────────┼───────────────────┼─────────────┘
          │                │                │                   │
          ▼                ▼                ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Storage Layer                                   │
│                         (Volumes / Database)                                 │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │
│  │ /data/sar/   │ │ /data/weather│ │ /data/       │ │ /data/observations │  │
│  │              │ │              │ │ forecast/    │ │                    │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                   │
          └────────────────┴────────────────┴───────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Analysis Layer                                  │
│                    (Ice condition prediction/assessment)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Source 1: Satellite Imagery

### 1a: SAR Radar Imagery (Sentinel-1)

#### Purpose
Detect surface roughness on water bodies. Smooth ice appears dark, rough water/ice appears bright. Works through clouds, day and night.

#### Data Source
- **Provider:** Copernicus Data Space Ecosystem (dataspace.copernicus.eu)
- **Product:** Sentinel-1 GRD (Ground Range Detected)
- **Polarization:** VV (best for ice/water discrimination)
- **Mode:** IW (Interferometric Wide swath)
- **Coverage:** Sweden bbox (~10.5°E to 24.2°E, 55.3°N to 69.1°N)
- **Frequency:** Every 6 days per satellite (2 satellites = ~3 days)

#### Collection Strategy
- Daily cron job queries for new products
- Download GRD products from last 48 hours
- Store organized by date: `/data/sar/YYYY-MM-DD/`
- Track downloaded IDs to avoid duplicates

### 1b: Optical Imagery (Sentinel-2)

#### Purpose
Visual identification of ice, snow, and water. Provides color/spectral information. Limited to clear-sky, daytime conditions.

#### Data Source
- **Provider:** Copernicus Data Space Ecosystem (dataspace.copernicus.eu)
- **Product:** Sentinel-2 L2A (atmospherically corrected)
- **Bands:** RGB + NIR (useful for snow/ice indices)
- **Coverage:** Sweden bbox (~10.5°E to 24.2°E, 55.3°N to 69.1°N)
- **Frequency:** Every 5 days per satellite (2 satellites = ~2-3 days)
- **Limitation:** Cloud cover often >80% in Swedish winter

#### Collection Strategy
- Daily cron job queries for new products
- Filter by cloud cover (<30% over area of interest)
- Download L2A products from last 48 hours
- Store organized by date: `/data/optical/YYYY-MM-DD/`
- Track downloaded IDs to avoid duplicates

### API Details (both)
- OAuth2 authentication
- OData API for product search
- Direct HTTPS download

### Docker Service: `satellite-collector`
```yaml
satellite-collector:
  build: ./collectors/satellite
  environment:
    - COPERNICUS_USER
    - COPERNICUS_PASSWORD
  volumes:
    - ./data/sar:/data/sar
    - ./data/optical:/data/optical
    - ./state:/state
```

---

## Data Source 2: Weather Data (Historical/Current)

### Purpose
Temperature history is critical for ice formation. Need sustained cold periods for safe ice.

### Data Source
- **Provider:** SMHI (Swedish Meteorological and Hydrological Institute)
- **API:** SMHI Open Data API (opendata.smhi.se)
- **Parameters needed:**
  - Air temperature (hourly/daily)
  - Wind speed (affects ice quality)
  - Precipitation (snow on ice)
  - Cloud cover (radiation cooling)

### Collection Strategy
- Fetch hourly observations from weather stations near lakes
- Calculate "cold degree days" (cumulative freezing)
- Store as JSON/CSV: `/data/weather/YYYY-MM-DD/`

### API Details
- Free, no authentication required
- REST API with JSON responses
- Station-based observations

### Docker Service: `weather-collector`
```yaml
weather-collector:
  build: ./collectors/weather
  volumes:
    - ./data/weather:/data
```

---

## Data Source 3: Weather Forecasts

### Purpose
Predict future ice conditions based on expected temperatures.

### Data Source
- **Provider:** SMHI
- **API:** SMHI Open Data - PMP (Point Meteorological Prognosis)
- **Forecast horizon:** Up to 10 days
- **Parameters:**
  - Temperature forecast
  - Wind forecast
  - Precipitation forecast

### Collection Strategy
- Fetch forecasts 2x daily (morning/evening updates)
- Store with timestamp: `/data/forecast/YYYY-MM-DD-HH/`
- Keep historical forecasts for accuracy analysis

### Docker Service: `forecast-collector`
```yaml
forecast-collector:
  build: ./collectors/forecast
  volumes:
    - ./data/forecast:/data
```

---

## Data Source 4: Observations & Excursion Reports

### Purpose
Ground truth from skaters. Validates predictions and provides real conditions.

### Potential Data Sources
- **Skridskonet** (skridskonat.se) - Swedish skating community reports
- **Skatopia** - Ice reports
- **Manual input** - User-submitted observations

### Data Points
- Location (lake/coordinates)
- Date/time
- Ice thickness (if measured)
- Ice quality (smooth, rough, snow-covered)
- Safety assessment
- Photos

### Collection Strategy
- Scrape/API from community sites (if available)
- Store structured reports: `/data/observations/YYYY-MM-DD/`
- Link observations to SAR imagery and weather data

### Docker Service: `observation-collector`
```yaml
observation-collector:
  build: ./collectors/observations
  volumes:
    - ./data/observations:/data
```

---

## Data Assembly & Analysis

### Lake Database
Maintain a database of Swedish lakes with:
- Name and ID
- Coordinates/polygon
- Typical freezing patterns
- Historical observations

### Time Series Data Model

All data must be stored in a clear time series format to enable learning and backtesting.

```
/data/
├── timeseries/
│   └── {lake_id}/
│       ├── sar/
│       │   └── {timestamp}.json        # SAR backscatter values
│       ├── optical/
│       │   └── {timestamp}.json        # Optical indices/features
│       ├── weather/
│       │   └── {timestamp}.json        # Temperature, wind, precip
│       ├── forecast/
│       │   └── {timestamp}.json        # Forecast at time of prediction
│       ├── observations/
│       │   └── {timestamp}.json        # Ground truth reports
│       └── predictions/
│           └── {timestamp}.json        # AI predictions + prompt used
```

Each record includes:
- `timestamp`: ISO 8601 datetime
- `lake_id`: Reference to lake
- `data`: Source-specific values
- `metadata`: Source, quality flags, etc.

---

## AI Prediction System

### Overview
Use an LLM to analyze satellite imagery, weather data, and forecasts to predict future ice conditions. The system learns over time by comparing predictions to actual observations.

### Prediction Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                        Daily Prediction                          │
│                                                                  │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌─────────────┐  │
│  │ SAR      │ + │ Optical  │ + │ Weather  │ + │ Forecast    │  │
│  │ imagery  │   │ imagery  │   │ history  │   │ (next 7d)   │  │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └──────┬──────┘  │
│       └──────────────┴──────────────┴────────────────┘          │
│                              │                                   │
│                              ▼                                   │
│                     ┌────────────────┐                          │
│                     │  Build Prompt  │◀── System Prompt         │
│                     │  + Context     │    (evolving)            │
│                     └───────┬────────┘                          │
│                             │                                    │
│                             ▼                                    │
│                     ┌────────────────┐                          │
│                     │   LLM (Claude) │                          │
│                     └───────┬────────┘                          │
│                             │                                    │
│                             ▼                                    │
│                     ┌────────────────┐                          │
│                     │  Prediction    │──▶ Store with timestamp  │
│                     │  (per lake)    │    + prompt version      │
│                     └────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘

                              │
                              │ Wait for observations
                              ▼

┌─────────────────────────────────────────────────────────────────┐
│                      Feedback Loop                               │
│                                                                  │
│  ┌────────────────┐        ┌────────────────┐                   │
│  │  Prediction    │   vs   │  Actual        │                   │
│  │  (from N days  │        │  Observation   │                   │
│  │   ago)         │        │  (today)       │                   │
│  └───────┬────────┘        └───────┬────────┘                   │
│          └─────────────┬───────────┘                            │
│                        │                                         │
│                        ▼                                         │
│               ┌────────────────┐                                │
│               │  Evaluate      │                                │
│               │  Accuracy      │                                │
│               └───────┬────────┘                                │
│                       │                                          │
│                       ▼                                          │
│               ┌────────────────┐                                │
│               │  Update        │──▶ Store learnings             │
│               │  System Prompt │    + accuracy metrics          │
│               └────────────────┘                                │
└─────────────────────────────────────────────────────────────────┘
```

### Prediction Storage

Each prediction record:
```json
{
  "timestamp": "2024-01-15T06:00:00Z",
  "lake_id": "vanern",
  "prediction": {
    "ice_present": true,
    "ice_quality": "smooth",
    "confidence": 0.8,
    "trend": "stable",
    "valid_until": "2024-01-18T00:00:00Z"
  },
  "inputs": {
    "sar_timestamp": "2024-01-14T05:30:00Z",
    "optical_timestamp": null,
    "weather_range": ["2024-01-08", "2024-01-14"],
    "forecast_timestamp": "2024-01-14T12:00:00Z"
  },
  "prompt_version": "v3",
  "prompt_hash": "abc123..."
}
```

### Prompt Evolution

Store prompt versions with:
```
/data/prompts/
├── v1.md                    # Initial prompt
├── v2.md                    # After first learnings
├── v3.md                    # Current version
└── evolution_log.json       # Why each change was made
```

Evolution log tracks:
- What predictions failed
- What patterns were missed
- What adjustments improved accuracy
- Accuracy metrics per prompt version

### Evaluation Metrics

When observations arrive, score predictions:
- **Ice presence accuracy**: Did we correctly predict ice/no ice?
- **Quality accuracy**: Did we predict the right quality?
- **Trend accuracy**: Did conditions change as predicted?
- **Lead time**: How far ahead were accurate predictions?

### Learning Process

1. **Collect failures**: When prediction ≠ observation
2. **Analyze patterns**: What input signals were missed?
3. **Hypothesize**: What prompt changes might help?
4. **Update prompt**: Add new rules/examples
5. **Track results**: Did accuracy improve?

---

## File Structure

```
nordic-ice/
├── docker-compose.yml          # All services
├── .env.example                 # Environment template
├── .env                         # Credentials (gitignored)
│
├── collectors/
│   ├── satellite/               # Sentinel-1 SAR + Sentinel-2 optical
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── config.py
│   │       ├── copernicus_client.py
│   │       └── download.py
│   │
│   ├── weather/                 # SMHI weather collector
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── config.py
│   │       ├── smhi_client.py
│   │       └── fetch.py
│   │
│   ├── forecast/                # SMHI forecast collector
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       └── fetch.py
│   │
│   └── observations/            # Community reports collector
│       ├── Dockerfile
│       ├── requirements.txt
│       └── src/
│           └── scrape.py
│
├── analysis/                    # Data assembly
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── lakes.py             # Lake database
│       ├── correlate.py         # Data assembly
│       └── timeseries.py        # Build per-lake time series
│
├── predictor/                   # AI prediction system
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── predict.py           # Run predictions via LLM
│       ├── evaluate.py          # Compare predictions to observations
│       ├── prompt_manager.py    # Version and evolve prompts
│       └── metrics.py           # Track accuracy over time
│
├── data/                        # All collected data (volume)
│   ├── sar/                     # Sentinel-1 radar (raw)
│   ├── optical/                 # Sentinel-2 optical (raw)
│   ├── weather/                 # SMHI observations (raw)
│   ├── forecast/                # SMHI forecasts (raw)
│   ├── observations/            # Skating reports (raw)
│   ├── timeseries/              # Processed per-lake time series
│   │   └── {lake_id}/
│   │       ├── sar/
│   │       ├── optical/
│   │       ├── weather/
│   │       ├── forecast/
│   │       ├── observations/
│   │       └── predictions/
│   └── prompts/                 # Prompt versions + evolution log
│       ├── v1.md
│       └── evolution_log.json
│
├── state/                       # Collector state (volume)
│
└── logs/                        # Service logs (volume)
```

---

## Implementation Order

### Phase 1: Satellite Collector
1. Copernicus API authentication
2. Product search and download (SAR + optical)
3. State management
4. Docker container with cron

### Phase 2: Weather Collector
1. SMHI API client
2. Fetch station observations
3. Calculate cold degree days
4. Docker container with cron

### Phase 3: Forecast Collector
1. SMHI forecast API
2. Fetch and store predictions
3. Docker container with cron

### Phase 4: Observation Collector
1. Research available APIs/scraping options
2. Implement data extraction
3. Normalize report format
4. Docker container with cron

### Phase 5: Data Assembly
1. Lake database with polygons
2. Extract SAR/optical values per lake
3. Correlate with weather/forecasts
4. Link observations to lakes
5. Build per-lake time series

### Phase 6: AI Prediction System
1. Initial prediction prompt
2. Run daily predictions via LLM
3. Store predictions with metadata
4. Evaluation against observations
5. Accuracy tracking
6. Prompt evolution workflow

---

## Backlog

### Epic: Data Collection

Automated collection of all data sources required for ice condition analysis.

---

#### Story 1: Satellite Image Collector

**As a** system operator
**I want** automated daily download of Sentinel-1 SAR and Sentinel-2 optical images over Sweden
**So that** we have satellite imagery to detect ice on lakes

**Tasks:**

- [ ] Set up Copernicus Data Space account and obtain API credentials
- [ ] Implement OAuth2 authentication with token refresh
- [ ] Implement OData API search for Sentinel-1 GRD products
- [ ] Implement OData API search for Sentinel-2 L2A products (with cloud filter)
- [ ] Implement product download with progress and retry logic
- [ ] Add state management (track downloaded product IDs for both)
- [ ] Create Dockerfile with Python and cron
- [ ] Create crontab for daily execution (06:00 UTC)
- [ ] Add logging to file
- [ ] Write docker-compose service definition
- [ ] Test end-to-end: build, run, verify downloads (SAR + optical)

---

#### Story 2: Weather Data Collector

**As a** system operator
**I want** automated collection of weather observations from SMHI
**So that** we have temperature history to assess ice formation

**Tasks:**

- [ ] Research SMHI Open Data API structure and endpoints
- [ ] Identify weather stations relevant to major lakes
- [ ] Implement API client for fetching observations
- [ ] Fetch parameters: temperature, wind, precipitation, cloud cover
- [ ] Calculate and store cold degree days per station
- [ ] Create Dockerfile with Python and cron
- [ ] Create crontab for hourly execution
- [ ] Add logging to file
- [ ] Write docker-compose service definition
- [ ] Test end-to-end: build, run, verify data

---

#### Story 3: Weather Forecast Collector

**As a** system operator
**I want** automated collection of weather forecasts from SMHI
**So that** we can predict future ice conditions

**Tasks:**

- [ ] Research SMHI PMP (Point Meteorological Prognosis) API
- [ ] Define grid points or locations to fetch forecasts for
- [ ] Implement API client for fetching forecasts
- [ ] Fetch parameters: temperature, wind, precipitation (10-day horizon)
- [ ] Store forecasts with timestamp for historical comparison
- [ ] Create Dockerfile with Python and cron
- [ ] Create crontab for 2x daily execution (06:00, 18:00 UTC)
- [ ] Add logging to file
- [ ] Write docker-compose service definition
- [ ] Test end-to-end: build, run, verify data

---

#### Story 4: Observation & Report Collector

**As a** system operator
**I want** automated collection of skating observations and excursion reports
**So that** we have ground truth data to validate predictions

**Tasks:**

- [ ] Research Skridskonet data availability (API or scraping)
- [ ] Research other sources: Skatopia, forums, social media
- [ ] Define normalized observation schema (location, date, thickness, quality)
- [ ] Implement scraper/API client for primary source
- [ ] Parse and normalize observation data
- [ ] Store structured reports as JSON
- [ ] Create Dockerfile with Python and cron
- [ ] Create crontab for hourly execution
- [ ] Add logging to file
- [ ] Write docker-compose service definition
- [ ] Test end-to-end: build, run, verify data

---

### Epic: Data Assembly

Correlate and combine data from all sources per lake for analysis.

*To be broken down after Data Collection epic is complete.*

- Lake database with polygons/coordinates
- Extract SAR backscatter values per lake
- Link weather data to lake locations
- Link forecasts to lake locations
- Match observations to lakes
- Unified data model per lake per day

---

### Epic: AI Prediction System

LLM-based prediction with iterative prompt improvement.

*To be broken down after Data Assembly epic is complete.*

- Build prediction prompt with satellite + weather context
- Run daily predictions per lake
- Store predictions with prompt version and inputs
- Evaluate predictions against incoming observations
- Track accuracy metrics per prompt version
- Prompt evolution workflow (analyze failures → update prompt)
- Learning feedback loop automation

---

## Verification

1. Start all collectors: `docker compose up -d`
2. Verify data appearing in `/data/` directories
3. Check logs: `docker compose logs -f`
4. Run analysis manually and verify output
