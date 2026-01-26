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

### Data Correlation
For each lake, assemble:
1. Latest SAR backscatter values (extract from imagery)
2. Temperature history (cold degree days)
3. Current forecast (will it stay frozen?)
4. Recent observations (ground truth)

### Ice Status Model
Combine inputs to estimate:
- **Ice presence:** Yes/No/Uncertain
- **Ice quality:** Smooth/Rough/Snow-covered
- **Trend:** Improving/Stable/Deteriorating
- **Confidence:** Based on data freshness and agreement

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
├── analysis/                    # Data analysis/prediction
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── lakes.py             # Lake database
│       ├── correlate.py         # Data assembly
│       └── predict.py           # Ice status model
│
├── data/                        # All collected data (volume)
│   ├── sar/                     # Sentinel-1 radar
│   ├── optical/                 # Sentinel-2 optical
│   ├── weather/
│   ├── forecast/
│   └── observations/
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
2. Extract SAR values per lake
3. Correlate with weather/forecasts
4. Link observations

### Phase 6: Analysis/Prediction
1. Simple rule-based model initially
2. Combine indicators into status
3. Output per-lake assessment

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

### Epic: Analysis & Prediction

Analyze assembled data to predict ice conditions and quality.

*To be broken down after Data Assembly epic is complete.*

- Ice presence detection model
- Ice quality classification
- Trend analysis (improving/deteriorating)
- Confidence scoring
- Output format (API, reports, maps)

---

## Verification

1. Start all collectors: `docker compose up -d`
2. Verify data appearing in `/data/` directories
3. Check logs: `docker compose logs -f`
4. Run analysis manually and verify output
