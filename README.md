# ChainWatch — National Crypto-Threat Intelligence Network

> **NTRO Proof of Concept** · Offline AI-driven blockchain forensics platform for detecting illicit cryptocurrency activity across Indian jurisdictions.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Repository Structure](#3-repository-structure)
4. [Technology Stack](#4-technology-stack)
5. [Data Flow — End to End](#5-data-flow--end-to-end)
6. [Service 1 — Streamlit Data Generator](#6-service-1--streamlit-data-generator)
7. [Service 2 — FastAPI Core Engine](#7-service-2--fastapi-core-engine)
   - [IP & ASN Geolocation Subsystem](#71-ip--asn-geolocation-subsystem)
   - [ML Pipeline](#72-ml-pipeline)
   - [REST API Reference](#73-rest-api-reference)
   - [Data Models](#74-data-models)
8. [Service 3 — React Frontend](#8-service-3--react-frontend)
   - [Routing](#81-routing)
   - [Home Dashboard](#82-home-dashboard)
   - [Analyst Workspace](#83-analyst-workspace)
   - [Component Reference](#84-component-reference)
   - [Map Utilities](#85-map-utilities)
9. [Persisted Data Files](#9-persisted-data-files)
10. [Infrastructure — Docker & Neo4j](#10-infrastructure--docker--neo4j)
11. [Setup & Installation](#11-setup--installation)
12. [Running the Project](#12-running-the-project)
13. [Stopping the Project](#13-stopping-the-project)
14. [Configuration Reference](#14-configuration-reference)
15. [Threat Classification Model](#15-threat-classification-model)
16. [PDF Dossier Generation](#16-pdf-dossier-generation)
17. [Security & Privacy Notes](#17-security--privacy-notes)
18. [Known Limitations & Future Work](#18-known-limitations--future-work)

---

## 1. Project Overview

ChainWatch is a fully **offline** threat intelligence platform built as an NTRO proof of concept. It ingests a Bitcoin-style transaction ledger (CSV), runs a two-stage unsupervised machine learning pipeline to identify anomalous wallet behaviour, enriches each result with geolocation and ASN data, and presents everything in an interactive React dashboard backed by a map of India.

**Core capabilities:**

- Synthetic ledger generation with planted anomalies targeting any of India's 36 states and union territories
- Offline IP-to-geolocation resolution using MaxMind MMDB databases and a fallback CSV range table
- Offline ASN/ISP enrichment using a DB-IP ASN Lite CSV
- Dual ML detection: Isolation Forest (anomaly scoring) + K-Means (behavioural clustering)
- Interactive choropleth-style map of India with per-wallet threat dots
- Infinite-scroll threat ticker, metric summary cards, and filterable alert watchlist
- Analyst Workspace with live engine logs, geospatial isolation view, and per-suspect detail cards
- One-click PDF dossier generation styled as an official NTRO intelligence record

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                             │
│                                                                 │
│   ┌─────────────────────┐      ┌──────────────────────────┐    │
│   │   React + Vite      │      │   Streamlit Generator    │    │
│   │   (port 5173)       │      │   (port 8501)            │    │
│   │                     │      │                          │    │
│   │  Home Dashboard     │      │  Synthetic ledger UI     │    │
│   │  Analyst Workspace  │      │  → downloads ledger.csv  │    │
│   └────────┬────────────┘      └──────────────────────────┘    │
│            │ REST / HTTP                                        │
└────────────┼────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│   FastAPI Core Engine          │
│   (port 8000)                  │
│                                │
│   POST /api/v1/ingest          │  ← receives ledger.csv
│     └─ Feature engineering     │
│     └─ IP/ASN lookup           │  ← MaxMind MMDB + CSV ranges
│     └─ Isolation Forest        │
│     └─ K-Means clustering      │
│     └─ Writes JSON outputs     │
│                                │
│   GET  /api/v1/anomalies       │  ← serves anomaly_results.json
│   GET  /api/v1/stats           │  ← serves stats.json
│   GET  /api/v1/report/{id}     │  ← generates & streams PDF
└────────────────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│   Local File System            │
│   anomaly_results.json         │
│   stats.json                   │
│   NTRO_Report_*.pdf            │
└────────────────────────────────┘
             │  (optional, not yet wired)
             ▼
┌────────────────────────────────┐
│   Neo4j 5.12 (Docker)          │
│   port 7474 (browser UI)       │
│   port 7687 (Bolt)             │
│   Wallet → TX → Wallet graphs  │
└────────────────────────────────┘
```

All three application services run **locally** with no outbound network calls. The MaxMind databases, ASN CSV, and GeoJSON map data are loaded from disk.

---

## 3. Repository Structure

```
chainwatch/
├── Start.sh                        # Launch all 3 services in parallel
├── Kill.sh                         # Graceful teardown of all services
├── docker-compose.yml              # Neo4j graph database
├── IP_Address.csv                  # India IP range → state/city/lat/lng lookup table
├── dbip-asn-lite-2026-09.csv       # DB-IP ASN Lite: IP range → ASN/org
├── india.geojson                   # India state boundaries (TopoJSON-compatible)
├── logs/
│   ├── backend.log                 # FastAPI stdout/stderr
│   ├── generator.log               # Streamlit stdout/stderr
│   └── frontend.log                # Vite dev server stdout/stderr
│
├── chainwatch_backend/
│   ├── main.py                     # FastAPI application — all endpoints + ML pipeline
│   ├── generator_app.py            # Streamlit synthetic ledger generator
│   ├── anomaly_results.json        # Output: flagged wallets (written by /ingest)
│   ├── stats.json                  # Output: aggregate metrics + all wallet locations
│   ├── venv/                       # Python virtual environment
│   └── database/                   # (expected) MaxMind MMDB files
│       ├── GeoIP-City.mmdb
│       └── GeoIP-ASN.mmdb
│
└── chainwatch_frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── main.jsx                # React entry point
        ├── App.jsx                 # Router (/ and /workspace)
        ├── Home.jsx                # Executive Dashboard page
        ├── Workspace.jsx           # Analyst Workspace page
        ├── index.css               # Global styles (all custom CSS lives here)
        ├── mapUtils.js             # Geospatial helpers: dot placement, state centers
        ├── india.json              # India GeoJSON bundled with frontend
        └── components/
            ├── MetricCards.jsx     # Summary KPI strip
            ├── AlertTable.jsx      # Threat watchlist rows
            ├── GraphView.jsx       # Force-directed wallet/TX/IP graph (react-force-graph-2d)
            └── ChartsView.jsx      # Pie + Bar charts (recharts)
```

---

## 4. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend framework** | React | 19.2 | UI |
| **Frontend build** | Vite | 8.2 | Dev server & bundler |
| **Routing** | react-router-dom | 7.18 | SPA routing |
| **Maps** | react-simple-maps | 3.0 | SVG choropleth map |
| **Graph viz** | react-force-graph-2d | 1.29 | Wallet/TX force graph |
| **Charts** | recharts | 3.10 | Pie & bar charts |
| **Backend framework** | FastAPI | latest | REST API |
| **ASGI server** | Uvicorn | latest | HTTP server with --reload |
| **Data processing** | pandas, numpy | latest | CSV parsing, feature vectors |
| **ML — anomaly** | scikit-learn IsolationForest | latest | Unsupervised outlier detection |
| **ML — clustering** | scikit-learn KMeans | latest | Behavioural grouping |
| **Geolocation (primary)** | maxminddb | latest | Reads MaxMind MMDB files |
| **Geolocation (fallback)** | IP_Address.csv + bisect | built-in | IP range → state/lat/lng |
| **ASN enrichment** | dbip-asn-lite CSV + bisect | built-in | IP range → ASN/org |
| **PDF generation** | WeasyPrint | latest | HTML → PDF conversion |
| **Data generation** | Streamlit + Faker | latest | Synthetic ledger UI |
| **Graph database** | Neo4j 5.12 | Docker | Wallet relationship storage |
| **Containerisation** | Docker Compose | 3.8 | Neo4j service |

---

## 5. Data Flow — End to End

```
Step 1  GENERATE
        Analyst opens Streamlit (port 8501)
        Selects a target Indian state
        Clicks "Generate 1,000 Transactions"
        → 950 normal Pareto-distributed retail txns
        → 50 high-volume anomalous txns concentrated in the target state
        Downloads ledger.csv

Step 2  INGEST
        Analyst opens Workspace (React, /workspace)
        Selects ledger.csv → clicks "RUN AI PIPELINE"
        Frontend POSTs multipart/form-data to POST /api/v1/ingest

Step 3  FEATURE ENGINEERING (backend)
        CSV rows are iterated; for each transaction:
          - input_addresses and input_amounts are parsed (ast.literal_eval)
          - src_ip is resolved via lookup_ip() → state, city, ASN, org, lat, lng
          - wallet_stats accumulates: tx_count, volume, unique IPs, states, ASNs, locations

Step 4  ML PIPELINE (backend)
        Feature matrix X = [tx_count, total_volume, unique_ip_count] per wallet
        StandardScaler normalises X
        IsolationForest (200 trees, 10% contamination) → anomaly labels + decision scores
        KMeans (up to 6 clusters) → cluster assignment per wallet

Step 5  RESULT BUILDING (backend)
        Flagged wallets (label == -1) are scored 60–99% confidence
        Primary state, ASN, ISP derived via Counter.most_common
        Mean lat/lng computed across all resolved locations
        Results sorted descending by confidence_score
        Written to anomaly_results.json and stats.json

Step 6  DISPLAY (frontend)
        Workspace fetches /api/v1/anomalies → renders suspect list
        Home Dashboard fetches /api/v1/stats and /api/v1/anomalies
        MetricCards shows total_transactions, total_wallets, anomalies_detected
        Map renders per-wallet threat dots (red = ≥85% confidence, amber = below)
        Threat ticker scrolls detected wallets
        Clicking a dot or alert row cross-highlights map and list

Step 7  REPORTING
        Analyst clicks "📄 Generate PDF" on any suspect
        Frontend opens GET /api/v1/report/{wallet_address} in a new tab
        Backend renders HTML dossier → WeasyPrint → streams PDF download
```

---

## 6. Service 1 — Streamlit Data Generator

**File:** `chainwatch_backend/generator_app.py`  
**URL:** `http://localhost:8501`

### Purpose

Produces a synthetic CSV ledger that mimics Bitcoin-style network traffic. It seeds a statistically realistic dataset with normal background traffic plus a planted anomaly cluster, giving the ML pipeline a meaningful signal to find.

### Key Design Decisions

- **Wallet pool of 150 addresses** — generated once via `fake.sha256()[:34]`; reused across rows to create realistic repeat-actor patterns.
- **3 threat wallets** — randomly sampled from the pool; these are the planted anomaly actors.
- **5% anomaly rate** — each row has a 5% chance of being flagged as an anomalous record. Anomalous rows use the 3 threat wallets, IPs sampled from the target state's ranges, and a `multiplier` of 10–50× normal volume.
- **Normal rows** use a random state, Pareto-like low volume (0.01–1.5 BTC multiplier), and 1–2 input wallets.
- **`dst_port: 8333`** — Bitcoin's default P2P port, used for all destination connections.
- **`@st.cache_data`** — both `load_ip_reference()` and `generate_data()` are cached; re-running with the same target state returns instantly from cache.

### Output Schema (`ledger.csv`)

| Column | Type | Description |
|---|---|---|
| `timestamp` | ISO 8601 string | Random datetime within the past ~7 days |
| `src_ip` | IPv4 string | Source IP sampled from state IP ranges |
| `dst_ip` | IPv4 string | Destination IP (any range) |
| `src_port` | int | Random ephemeral port (1024–65535) |
| `dst_port` | int | Always `8333` (Bitcoin P2P) |
| `txid` | hex string | UUID4 hex — unique transaction ID |
| `input_addresses` | Python list literal | 1–4 wallet addresses as a string |
| `output_addresses` | Python list literal | 1–2 wallet addresses as a string |
| `input_amounts` | Python list literal | BTC amounts per input address |
| `output_amounts` | Python list literal | BTC amounts per output address |
| `geo_state` | string | State name used as fallback in backend |

---

## 7. Service 2 — FastAPI Core Engine

**File:** `chainwatch_backend/main.py`  
**URL:** `http://localhost:8000`

### 7.1 IP & ASN Geolocation Subsystem

The backend resolves every `src_ip` to a geographic location and network identity using a layered fallback approach.

#### Layer 1 — MaxMind MMDB (primary)

Two MaxMind binary databases are loaded at startup:

```
chainwatch_backend/database/GeoIP-City.mmdb   → state, city, lat, lng
chainwatch_backend/database/GeoIP-ASN.mmdb    → ASN number, organisation name
```

If these files are absent, the backend logs a warning and falls back to CSV-only mode.

#### Layer 2 — `IP_Address.csv` (India-specific fallback)

A CSV at the project root maps Indian IP ranges to state, city, latitude, and longitude. Loaded once via `@lru_cache(maxsize=1)` into a sorted list of `(start_int, end_int, state, city, lat, lng)` tuples. Binary search (`bisect_right`) finds the matching range in O(log n).

**Required columns (case-insensitive, BOM-stripped):**

| Column | Description |
|---|---|
| `start` | IP range start (dotted-decimal) |
| `end` | IP range end (dotted-decimal) |
| `state` | Indian state or UT name |
| `city` | City name |
| `lat` | Latitude (float) |
| `long` | Longitude (float) |

#### Layer 3 — `dbip-asn-lite-2026-09.csv` (ASN fallback)

No-header CSV with columns `start, end, asn, org`. Same binary-search approach as the location CSV. Used when MaxMind ASN database is absent.

#### `lookup_ip(ip: str) → dict`

```python
{
  "state":     str,    # Indian state or "Unknown"
  "city":      str,    # City or "Unknown"
  "asn":       str,    # "AS12345" or "N/A"
  "org":       str,    # ISP/org name or "N/A"
  "latitude":  float | None,
  "longitude": float | None
}
```

Private/reserved IP addresses (`address.is_global == False`) return the default empty result immediately without any lookup.

---

### 7.2 ML Pipeline

Executed inside `POST /api/v1/ingest` after feature engineering.

#### Feature Engineering

Per-wallet aggregate features are built in a single pass over the CSV:

```python
features = [
    wallet.tx_count,          # Number of transactions involving this wallet
    wallet.total_volume,      # Sum of all BTC amounts
    len(wallet.unique_ips)    # Number of distinct source IPs
]
```

These three dimensions capture the core behaviours of interest: frequency, scale, and network dispersion.

#### Stage 1 — Isolation Forest

```python
IsolationForest(
    n_estimators=200,      # 200 trees for stable scores on small datasets
    contamination=0.10,    # Expects ~10% of wallets to be anomalous
    random_state=42
)
```

- Returns `label == -1` for outliers (anomalous wallets)
- `decision_function()` returns a continuous score; more negative = more anomalous
- Confidence is mapped linearly from the score range → **60–99%** band

**Confidence formula:**

```python
conf = 60 + 39 * (hi - iso_score[i]) / score_range
```

Where `hi` is the highest anomaly score among flagged wallets (least anomalous flagged), and `lo` is the lowest (most anomalous). This ensures the most deviant wallet gets ~99% and the marginal case gets ~60%.

#### Stage 2 — K-Means Clustering

```python
KMeans(
    n_clusters=min(6, len(wallets)),
    random_state=42,
    n_init=10
)
```

Runs on all wallets (not just flagged ones). Each flagged wallet is tagged with its cluster ID and a human-readable name from:

```python
CLUSTER_NAMES = [
    "Micro-Transactor Ring",
    "High-Volume Laundering Node",
    "Multi-Hop Relay Cluster",
    "Dormant-then-Active",
    "Cross-Border Cell",
    "Retail Node"
]
```

The cluster name is assigned by index only; it is a label applied to the K-Means partition — it does not independently classify behaviour.

---

### 7.3 REST API Reference

#### `GET /`
Health check.

**Response:**
```json
{ "status": "ChainWatch Engine Active" }
```

---

#### `GET /api/v1/stats`
Returns the aggregate metrics and all wallet locations from the last ingest run.

**Response:**
```json
{
  "total_transactions": 1000,
  "total_wallets": 148,
  "anomalies_detected": 14,
  "wallet_locations": [
    {
      "wallet_address": "abc123...",
      "primary_state": "Maharashtra",
      "is_threat": true,
      "confidence_score": 91.4,
      "latitude": 19.7515,
      "longitude": 75.7139
    }
  ]
}
```

`wallet_locations` contains **all** wallets (not just flagged), so the frontend can render both threat dots (red/amber) and normal dots (blue).

---

#### `GET /api/v1/anomalies`
Returns the list of flagged wallets sorted by descending confidence score.

**Response:** `Array<AnomalyAlert>`

```json
[
  {
    "wallet_address": "1A2b3C...",
    "confidence_score": 97.3,
    "cluster_id": 1,
    "cluster_name": "High-Volume Laundering Node",
    "reason": "AI detected 42 rapid TXNs masking 1823.40 BTC across 38 distinct IPs.",
    "tx_count": 42,
    "total_volume_btc": 1823.4,
    "unique_ip_count": 38,
    "primary_state": "Maharashtra",
    "asn": "AS9829",
    "isp": "BSNL",
    "lat": 19.0760,
    "lng": 72.8777
  }
]
```

---

#### `POST /api/v1/ingest`
Accepts a `multipart/form-data` upload with a single field `file` containing the `ledger.csv`.

Runs the full ML pipeline and overwrites `anomaly_results.json` and `stats.json`.

**Request:** `Content-Type: multipart/form-data`, field name `file`

**Response:**
```json
{
  "message": "Ingestion and ML Analysis Complete",
  "anomalies_found": 14
}
```

**Error responses:**
- `500` if the CSV cannot be parsed or the ML pipeline fails

---

#### `GET /api/v1/report/{wallet_id}`
Generates and streams a PDF intelligence dossier for the specified wallet address.

**Path parameter:** `wallet_id` — full wallet address string

**Response:** `application/pdf` stream, filename `NTRO_Threat_Report_{wallet_id[:8]}.pdf`

**Error responses:**
- `404` — wallet not found in `anomaly_results.json`
- `500` — PDF generation error

---

### 7.4 Data Models

#### `AnomalyAlert` (Pydantic)

```python
class AnomalyAlert(BaseModel):
    wallet_address:    str
    confidence_score:  float           # 60.0 – 99.0
    cluster_id:        int             # 0 – 5
    cluster_name:      str
    reason:            str             # Human-readable ML rationale
    tx_count:          int
    total_volume_btc:  float
    unique_ip_count:   int
    primary_state:     Optional[str]   # Most frequent state from Counter
    asn:               Optional[str]   # e.g. "AS9829"
    isp:               Optional[str]   # e.g. "BSNL"
    lat:               Optional[float] # Mean latitude of all resolved IPs
    lng:               Optional[float] # Mean longitude of all resolved IPs
```

---

## 8. Service 3 — React Frontend

**Directory:** `chainwatch_frontend/`  
**URL:** `http://localhost:5173`

### 8.1 Routing

`App.jsx` defines two routes:

| Path | Component | Description |
|---|---|---|
| `/` | `Home` | Executive Dashboard |
| `/workspace` | `Workspace` | Analyst Workspace |

---

### 8.2 Home Dashboard

**File:** `src/Home.jsx`

The primary stakeholder-facing view. It has no state persistence — all data is fetched fresh on mount.

#### Data Fetching

A shared `useAPI(endpoint)` hook wraps `fetch` + `useState` + `useEffect`:

```js
function useAPI(endpoint) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetch(`${API}${endpoint}`)
      .then(r => r.json())
      .then(setData)
      .finally(() => setLoading(false));
  }, [endpoint]);
  return { data, loading };
}
```

Two calls are made in parallel on mount: `/stats` and `/anomalies`.

#### Sections (top to bottom)

| Section | Description |
|---|---|
| **Accessibility bar** | Skip-to-content link; A- / A / A+ zoom controls |
| **Topbar** | GOI emblem, NTRO brand, system title, offline badge, "Ingest New Ledger" CTA |
| **Live threat banner** | Conditionally rendered red alert strip (triggered by double-clicking the brand area during a demo, populates from `alerts[0]`) |
| **Hero section** | Full-width image with title and subtitle overlay |
| **Threat ticker** | Infinite horizontally-scrolling strip of alert cards; pauses when `liveThreatData` is set |
| **MetricCards** | Three KPI cards: transactions analysed, unique wallets, threats isolated |
| **Regional Threat Map** | Interactive SVG map of India; click a state to filter; threat dots coloured by confidence |
| **Threat Watchlist** | `AlertTable` filtered by selected state or showing all |
| **Footer** | About, Quick Links, Nodal Agency address columns |

#### State Interactions

- Clicking a state on the map → `setSelectedState(stateName)` → filters both the alert table and the map dots
- Clicking a wallet in the alert table → `handleAlertSelect(wallet_address)` → sets `highlightedWallet` and auto-pans the map to the wallet's state
- Clicking a wallet dot on the map → same cross-highlight behaviour
- Clicking anywhere outside the map (and not on the alert panel) → clears `selectedState`

---

### 8.3 Analyst Workspace

**File:** `src/Workspace.jsx`

The operational interface for analysts running the ML pipeline.

#### Layout (3-pane)

```
┌──────────────┬──────────────────────────┬──────────────────┐
│  LEFT PANE   │      CENTER PANE         │   RIGHT PANE     │
│              │                          │                  │
│  1. DATA     │  2. GEOSPATIAL           │  3. REGIONAL     │
│  INGESTION   │     ISOLATION MAP        │     SUSPECTS     │
│              │                          │                  │
│  File picker │  Interactive India map   │  Per-suspect     │
│  Upload btn  │  (same as Home map)      │  detail cards    │
│              │                          │  + PDF button    │
│              ├──────────────────────────┤                  │
│              │  ENGINE LOGS terminal    │                  │
└──────────────┴──────────────────────────┴──────────────────┘
```

#### Upload Flow

1. Analyst selects a CSV via the hidden `<input type="file">`.
2. Clicks "RUN AI PIPELINE".
3. Frontend pushes a series of simulated log messages to the terminal with staggered `setTimeout` calls (1s, 2.5s, 4s, 5.5s intervals) to visualise pipeline stages.
4. A real `FormData` POST to `/api/v1/ingest` runs in parallel with the log simulation.
5. At t+7s, the real response is consumed — if success, `fetchAlerts()` repopulates the suspects panel; if error, a red error line is appended to the terminal.

#### Log Line Styling

| Prefix | CSS class | Colour |
|---|---|---|
| `[ERROR]` | `log-err` | Red |
| `[SUCCESS]` | `log-succ` | Green |
| Everything else | `log-info` | Muted grey |

#### PDF Generation

The "📄 Generate PDF" button opens `GET /api/v1/report/{wallet_address}` in a new browser tab, which triggers a PDF download directly from the backend.

---

### 8.4 Component Reference

#### `MetricCards`

**Props:** `{ stats: object | null }`

Renders three flat metric cards. While `stats` is null, shows "Loading metrics…". Each card reads:
- `stats.total_transactions` — formatted with `toLocaleString()`
- `stats.total_wallets`
- `stats.anomalies_detected` — highlighted in red

---

#### `AlertTable`

**Props:** `{ alerts, loading, selectedWallet, onSelectWallet }`

Flat list of threat records. Each row shows:
- File number (1-indexed rank)
- Confidence score
- Full wallet address
- Origin state, ISP/ASN, behavioural classification

Selected wallet row gets the `selected` CSS class. Clicking any row calls `onSelectWallet(wallet_address)`.

---

#### `GraphView`

**Props:** `{ data, loading, highlightNode }`

Wraps `react-force-graph-2d`. Not currently wired to any page route — available for integration.

**Node types and colours:**

| Type | Normal colour | Flagged colour | Meaning |
|---|---|---|---|
| `wallet` | `#138808` (GOI green) | `#FF9933` (saffron) | Bitcoin wallet address |
| `ip` | `#003366` (GOI blue) | `#cc0000` (red) | Source IP address |
| `transaction` | `#6b7280` (grey) | `#9ca3af` (light grey) | Transaction node |

**Highlight behaviour:** When `highlightNode` is set, all non-adjacent nodes fade to `rgba(200,200,200,0.2)` and links involving non-highlighted nodes fade to near-transparent. The camera animates (`centerAt` + `zoom(4)`) to the highlighted node.

**Link types and colours:**

| Link type | Colour |
|---|---|
| `BROADCASTED` | Blue 30% opacity |
| `SENT_TO_NODE` | Blue 15% opacity |
| `INPUT_TO_TX` | Teal 35% opacity |
| `OUTPUT_TO_WALLET` | Purple 35% opacity |

---

#### `ChartsView`

**Props:** `{ stats, clusters }`

Two side-by-side charts using Recharts. Not currently wired to any page route — available for integration.

- **Pie chart** — "Risk Distribution": normal wallets (GOI blue `#003366`) vs flagged wallets (saffron `#FF9933`). Donut style (innerRadius 60, outerRadius 80).
- **Bar chart** — "AI Cluster Threat Assessment": one bar per K-Means cluster, labelled by the first word of the cluster name. All bars in GOI deep blue.

Both charts use a custom tooltip showing the full cluster name and count.

---

### 8.5 Map Utilities

**File:** `src/mapUtils.js`

#### `getStateCenter(stateName, geoJson) → [lng, lat]`

Computes the bounding-box centroid of a state by collecting all coordinate pairs from its GeoJSON geometry, then averaging `(minLng + maxLng) / 2` and `(minLat + maxLat) / 2`. Falls back to `STATE_COORDS[stateName]` (a hardcoded lookup for 14 key states), then `[80, 22]` (geographic centre of India).

Used by the map's `ZoomableGroup.center` prop when a state is selected, animating a smooth zoom-in.

#### `getWalletDots(wallets, geoJson, highlightedWallet) → Array<dot>`

Places each wallet as a dot at a random point **guaranteed to lie within the state's polygon** (using a point-in-polygon ray-casting check, up to 10,000 attempts per wallet).

Uses a deterministic LCG PRNG (`randomState * 1664525 + 1013904223 mod 2^32`) so dot positions are stable across re-renders for the same data order.

**Dot object:**

```js
{
  id:          wallet_address,
  lng:         float,
  lat:         float,
  wallet:      wallet_address,
  state:       stateName,
  confidence:  float,     // 0–100
  highlighted: boolean,
  color:       string     // '#e86a6a' (≥85%), '#e9a24f' (<85% threat), '#4f8fc9' (normal)
}
```

#### `generateStateDots(stateName, count, geoJson)` / `generateAllStateDots(geoJson, countPerState)`

Helper functions for placing arbitrary dots within state boundaries, used for decorative background dots if needed.

#### `pointInGeometry(point, geometry)`

Ray-casting algorithm supporting both `Polygon` and `MultiPolygon` GeoJSON geometries. Used by `getWalletDots` to validate candidate dot positions.

---

## 9. Persisted Data Files

These JSON files act as the persistence layer between the backend ML pipeline and the frontend. They are plain files on disk — no database involved in the primary read/write path.

### `chainwatch_backend/anomaly_results.json`

Written by `POST /api/v1/ingest`. Array of `AnomalyAlert` objects (see §7.4), sorted by `confidence_score` descending.

### `chainwatch_backend/stats.json`

```json
{
  "total_transactions": 1000,
  "total_wallets": 148,
  "anomalies_detected": 14,
  "wallet_locations": [ ... ]
}
```

`wallet_locations` contains every wallet seen in the ingested ledger (not just flagged ones), with `is_threat: true/false` so the frontend can render both threat and normal dots on the map.

### `chainwatch_backend/NTRO_Report_*.pdf`

Temporary PDF files generated by `GET /api/v1/report/{wallet_id}`. Named `NTRO_Report_{wallet_id[:8]}.pdf`. Not cleaned up automatically between runs.

---

## 10. Infrastructure — Docker & Neo4j

**File:** `docker-compose.yml`

```yaml
services:
  neo4j:
    image: neo4j:5.12.0
    ports:
      - "7474:7474"   # Neo4j Browser UI
      - "7687:7687"   # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/hackathon2026
    volumes:
      - ./neo4j_data:/data
```

Neo4j is included for graph-based wallet relationship storage (multi-hop transaction chain traversal). It is **not yet wired** into the current FastAPI or frontend code — the `GraphView` component and `ChartsView` component are built and ready but not connected to a live data source.

**Neo4j credentials:**
- Username: `neo4j`
- Password: `hackathon2026`
- Browser: `http://localhost:7474`
- Bolt: `bolt://localhost:7687`

Start Neo4j independently with:
```bash
docker compose up -d
```

---

## 11. Setup & Installation

### Prerequisites

- Python 3.10+
- Node.js 20+
- Docker Desktop (for Neo4j, optional)
- fish shell (Start.sh uses `fish -c "source venv/bin/activate.fish; ..."`)

### Backend

```bash
cd chainwatch_backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate.fish   # fish shell
# OR: source venv/bin/activate  # bash/zsh

# Install dependencies
pip install fastapi uvicorn[standard] pandas numpy scikit-learn \
            maxminddb weasyprint streamlit faker
```

#### MaxMind Databases (optional but recommended)

Place your MaxMind binary databases at:
```
chainwatch_backend/database/GeoIP-City.mmdb
chainwatch_backend/database/GeoIP-ASN.mmdb
```

If absent, the backend falls back to CSV-based lookups. The fallback covers Indian IPs well via `IP_Address.csv`.

### Frontend

```bash
cd chainwatch_frontend
npm install
```

---

## 12. Running the Project

### Option A — All-in-one script (recommended)

From the project root:

```bash
./Start.sh
```

This launches all three services in parallel as background jobs:

| # | Service | URL | Log file |
|---|---|---|---|
| 1 | FastAPI backend | `http://localhost:8000` | `logs/backend.log` |
| 2 | Streamlit generator | `http://localhost:8501` | `logs/generator.log` |
| 3 | Vite frontend | `http://localhost:5173` | `logs/frontend.log` |

PIDs are written to `.chainwatch_pids` for clean teardown.

Monitor all logs live:
```bash
tail -f logs/*.log
```

### Option B — Manual (each service in a separate terminal)

**Terminal 1 — Backend:**
```bash
cd chainwatch_backend
source venv/bin/activate.fish
uvicorn main:app --reload
```

**Terminal 2 — Generator:**
```bash
cd chainwatch_backend
source venv/bin/activate.fish
streamlit run generator_app.py
```

**Terminal 3 — Frontend:**
```bash
cd chainwatch_frontend
npm run dev
```

### Option C — Neo4j (optional)

```bash
docker compose up -d
```

---

## 13. Stopping the Project

```bash
./Kill.sh
```

`Kill.sh` uses a two-strategy approach:

1. **PID file strategy** — reads `.chainwatch_pids`, sends `SIGTERM` to the entire process group of each recorded PID (catches uvicorn's reload subprocess and Vite's child node process). Escalates to `SIGKILL` after 1 second if the process is still alive.

2. **Pattern fallback** — runs `pkill -f` against `uvicorn main:app`, `streamlit run generator_app.py`, and `vite` to catch any processes that escaped their group.

---

## 14. Configuration Reference

All configuration is currently hardcoded. Key values to change for a new deployment:

| Location | Variable | Default | Description |
|---|---|---|---|
| `main.py` | `CITY_DB` | `database/GeoIP-City.mmdb` | MaxMind city database path |
| `main.py` | `ASN_DB` | `database/GeoIP-ASN.mmdb` | MaxMind ASN database path |
| `main.py` | `LOCATION_CSV` | `../IP_Address.csv` | India IP range CSV |
| `main.py` | `ASN_CSV` | `../dbip-asn-lite-2026-09.csv` | DB-IP ASN CSV |
| `main.py` | `contamination=0.10` | `0.10` | Expected anomaly fraction for Isolation Forest |
| `main.py` | `n_clusters=min(6, ...)` | `6` | Maximum K-Means clusters |
| `Home.jsx` | `API` | `http://localhost:8000/api/v1` | Backend base URL |
| `Workspace.jsx` | `API` | `http://localhost:8000/api/v1` | Backend base URL |
| `docker-compose.yml` | `NEO4J_AUTH` | `neo4j/hackathon2026` | Neo4j credentials |

---

## 15. Threat Classification Model

### Isolation Forest — How it works

An Isolation Forest builds an ensemble of random trees. Anomalies are points that require fewer splits to isolate — they land in short branches. The `decision_function` score is negative for anomalies; the more negative, the more isolated (anomalous) the wallet.

### Why these three features?

| Feature | What it detects |
|---|---|
| `tx_count` | Wallets with unusually high transaction frequency (rapid cycling) |
| `total_volume_btc` | Wallets moving disproportionately large amounts |
| `unique_ip_count` | Wallets operating from many different IPs (network dispersion, potential multi-hop relay) |

A structuring attack (breaking large amounts into many small transactions) would show high `tx_count` with moderate `total_volume`. A single large transfer would show low `tx_count` with high `total_volume`. Multi-hop relay nodes show high `unique_ip_count`. The combination makes the feature space non-trivial to game simultaneously.

### Cluster Names — Interpretation Guide

| Cluster | Typical profile |
|---|---|
| Micro-Transactor Ring | Many small-volume transactions across a tight wallet group |
| High-Volume Laundering Node | Few wallets, very high total BTC, concentrated IPs |
| Multi-Hop Relay Cluster | High unique IP count, moderate volume — acts as a pass-through |
| Dormant-then-Active | Low tx_count but unusually high single-burst volume |
| Cross-Border Cell | High IP diversity spanning multiple states |
| Retail Node | Normal baseline — mis-flagged by the 10% contamination parameter |

> Note: cluster-to-name assignment is by K-Means partition index, not by semantic classification. Treat cluster names as indicative labels, not definitive behavioural verdicts.

---

## 16. PDF Dossier Generation

`GET /api/v1/report/{wallet_id}` generates a single-page A4 PDF styled as an NTRO intelligence record.

**Sections in the dossier:**

| Section | Contents |
|---|---|
| Masthead | GOI / NTRO header with "RESTRICTED — THREAT INTELLIGENCE" classification banner |
| 01 / Subject Identification | Wallet address, behavioural classification, confidence score |
| 02 / Network and Geographic Footprint | Primary state, ISP/org, ASN number, record reference (`CW-{wallet[:12].upper()}`) |
| 03 / Analytical Evidence | Transaction count, total BTC volume, unique IP count, detection engine label, AI-generated reason text |
| Handling notice | Legal disclaimer clarifying the record is synthetic and not a criminal finding |

**Implementation:** WeasyPrint renders an in-memory HTML string to PDF. The PDF is saved to disk at `chainwatch_backend/NTRO_Report_{wallet_id[:8]}.pdf` and then streamed as a `FileResponse`.

All wallet data is HTML-escaped via `html.escape()` before insertion into the template to prevent injection in the rendered PDF.

---

## 17. Security & Privacy Notes

- **Fully offline** — no data leaves the local machine. The backend makes no outbound HTTP calls; all geolocation and ASN resolution uses local files.
- **CORS is wide open** (`allow_origins=["*"]`) — appropriate for a local development/demo setup only. Restrict to the frontend origin before any deployment.
- **No authentication** — all API endpoints are unauthenticated. Add an API key or session layer before exposing beyond localhost.
- **Synthetic data only** — the generator produces entirely fake wallet addresses, transaction IDs, and IP addresses. No real financial or personal data is processed in normal operation.
- **PDF HTML escaping** — all wallet fields are passed through `html.escape()` before being embedded in the PDF template.
- **Neo4j password** is stored in plain text in `docker-compose.yml`. Rotate before any shared or networked deployment.

---

## 18. Known Limitations & Future Work

| Item | Status | Notes |
|---|---|---|
| Neo4j graph integration | Not wired | `GraphView` and `ChartsView` components are complete; need a `/api/v1/graph/{wallet}` endpoint and ingestion step that writes to Neo4j |
| Real transaction data | Not supported | Would require a Bitcoin node or block explorer API integration |
| Authentication layer | Missing | Add JWT or session auth to all API endpoints |
| Persistent storage | JSON files only | Replace with a proper database (PostgreSQL or Neo4j) for multi-session history |
| Multi-file ingestion | Not supported | Currently each ingest overwrites previous results |
| PDF cleanup | Not implemented | Generated PDFs accumulate on disk; add a cleanup task |
| Streamlit ↔ Workspace integration | Manual step | Analyst must download CSV from Streamlit and manually upload in Workspace; a direct pipe would improve UX |
| `ChartsView` integration | Unused | Component exists but is not rendered on any current route |
| `GraphView` integration | Unused | Component exists but is not rendered on any current route |
| CORS restriction | Wide open | Restrict `allow_origins` to `["http://localhost:5173"]` for hardened local use |
| Contamination tuning | Hardcoded at 0.10 | Should be configurable or auto-tuned based on dataset size |

---

*ChainWatch — NTRO Proof of Concept · Cyber Intelligence Division*
