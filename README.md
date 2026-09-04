<div align="center">

<img src="https://upload.wikimedia.org/wikipedia/commons/5/55/Emblem_of_India.svg" height="80" alt="Emblem of India"/>

# ChainWatch

### National Crypto-Threat Intelligence Network
**Government of India · National Technical Research Organisation (NTRO)**

*Securing India's digital financial infrastructure through AI-driven blockchain forensics*

---

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19.x-61DAFB?style=flat-square&logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-8.x-646CFF?style=flat-square&logo=vite&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/Classification-RESTRICTED-cc0000?style=flat-square)

</div>

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Key Features](#key-features)
- [Technology Stack](#technology-stack)
- [Repository Structure](#repository-structure)
- [ML Pipeline Deep Dive](#ml-pipeline-deep-dive)
- [API Reference](#api-reference)
- [Frontend Application](#frontend-application)
- [Data Generator](#data-generator)
- [Getting Started](#getting-started)
- [Workflow Guide](#workflow-guide)
- [Threat Classification Model](#threat-classification-model)
- [PDF Intelligence Reports](#pdf-intelligence-reports)
- [Docker & Infrastructure](#docker--infrastructure)
- [Sample Data Output](#sample-data-output)
- [Known Limitations & Future Roadmap](#known-limitations--future-roadmap)

---

## Overview

ChainWatch is a fully **offline**, AI-powered cryptocurrency threat intelligence platform built as a proof-of-concept for the National Technical Research Organisation (NTRO). It monitors, detects, and analyzes illicit Bitcoin transaction patterns across all Indian jurisdictions — without any external network dependency.

The system ingests raw Bitcoin ledger data (CSV format), runs a two-stage machine learning pipeline (Isolation Forest + K-Means clustering), resolves geographic and ISP attribution via offline MaxMind databases, and surfaces flagged threat actors in a government-grade executive dashboard — complete with auto-generated classified PDF dossiers.

> **This is a Proof of Concept.** All transaction data is synthetically generated to simulate realistic financial crime patterns. No real transaction data is used.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ANALYST WORKFLOW                             │
│                                                                     │
│  ┌─────────────────┐     ledger.csv     ┌───────────────────────┐  │
│  │  Streamlit Data │ ──────────────────▶│  React Workspace UI   │  │
│  │  Generator App  │                    │  (Upload & Ingest)    │  │
│  └─────────────────┘                    └──────────┬────────────┘  │
│                                                    │ POST /ingest  │
│                                         ┌──────────▼────────────┐  │
│                                         │  FastAPI Core Engine  │  │
│                                         │  (Python Backend)     │  │
│                                         │  ┌─────────────────┐  │  │
│                                         │  │ Feature Eng.    │  │  │
│                                         │  │ IsolationForest │  │  │
│                                         │  │ K-Means Cluster │  │  │
│                                         │  │ GeoIP Resolve   │  │  │
│                                         │  └────────┬────────┘  │  │
│                                         └───────────┼───────────┘  │
│                                                     │              │
│                         ┌───────────────────────────┤              │
│                         │                           │              │
│              ┌──────────▼──────────┐   ┌────────────▼──────────┐  │
│              │  anomaly_results    │   │     stats.json        │  │
│              │       .json         │   │  (aggregate metrics)  │  │
│              └──────────┬──────────┘   └────────────┬──────────┘  │
│                         │                           │              │
│              ┌──────────▼───────────────────────────▼──────────┐  │
│              │         React Executive Dashboard (Home)        │  │
│              │  Metric Cards · Threat Map · Alert Table ·      │  │
│              │  Ticker · Live Threat Banner · PDF Reports       │  │
│              └───────────────────────────────────────────────  ┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Intelligence Dashboard
- **Government-grade UI** styled to NTRO/NIC standards with the Indian tricolor palette (Saffron `#FF9933`, White, Navy `#003366`)
- **Live Threat Ticker** — horizontal scrolling feed of all detected anomalies with wallet IDs, BTC volumes, and confidence scores
- **Live Threat Banner** — critical alert banner triggered when anomaly isolation is confirmed
- **Interactive India Map** — click any state to zoom in, filter alerts by that jurisdiction, and see scatter-plotted transaction origin points
- **Threat Watchlist** — sortable alert panel with file-style cards showing origin state, ISP/ASN attribution, and threat classification
- **Metric Cards** — real-time counts for Transactions Analyzed, Unique Wallets, and Threats Isolated
- **Accessibility Controls** — A- / A / A+ font scaling buttons and skip-to-content link

### Analyst Workspace
- **Drag-and-drop CSV ingestion** — upload a `ledger.csv` file directly through the browser
- **Simulated engine log terminal** — real-time log stream showing pipeline stages (GeoIP resolution → Isolation Forest → K-Means)
- **Geospatial Isolation Map** — state-level click-to-zoom with top anomaly states displayed
- **Regional Suspects Panel** — per-state filtered list of flagged wallets with volumes, ISP info, and one-click PDF generation
- **Top Anomaly States indicator** — live-computed ranking of most active threat jurisdictions

### ML Anomaly Engine
- **Two-stage detection:** Isolation Forest flags statistical outliers; K-Means clusters behavioral patterns
- **Feature engineering per wallet:** transaction count, total BTC volume, unique IP count
- **Confidence scoring:** mapped from Isolation Forest decision function to a human-readable 60–99% range
- **Six behavioral threat classes** (see [Threat Classification Model](#threat-classification-model))
- **Offline GeoIP & ASN resolution** via MaxMind `.mmdb` databases — no external API calls

### Data Generator
- **Streamlit app** for generating augmented synthetic Bitcoin ledger data
- **Power-law distribution** to mimic real financial behavior (80% normal retail, ~5% planted anomalies)
- **36 Indian states and UTs** supported as target jurisdictions
- **One-click CSV download** for immediate ingestion

### PDF Intelligence Dossiers
- Auto-generated **NTRO-classified PDF reports** for any flagged wallet
- Includes: wallet address, AI confidence score, behavioral classification, geographic jurisdiction, ISP/ASN attribution, and AI evidence log
- Styled as official government documents, subject to the Official Secrets Act disclaimer
- Generated on-demand via `GET /api/v1/report/{wallet_id}` and streamed directly to the browser

---

## Technology Stack

### Backend
| Component | Technology | Purpose |
|---|---|---|
| API Framework | FastAPI | REST API, file upload, response streaming |
| ML — Anomaly Detection | scikit-learn `IsolationForest` | Statistical outlier detection |
| ML — Clustering | scikit-learn `KMeans` | Behavioral pattern grouping |
| Data Processing | pandas, numpy | Feature engineering, CSV parsing |
| GeoIP Resolution | maxminddb + GeoIP-City.mmdb | Offline IP → Indian State mapping |
| ASN Resolution | maxminddb + GeoIP-ASN.mmdb | Offline IP → ISP/ASN mapping |
| PDF Generation | WeasyPrint | HTML-to-PDF classified report rendering |
| Data Models | Pydantic | Request/response validation |
| Preprocessing | scikit-learn `StandardScaler` | Feature normalization before ML |

### Frontend
| Component | Technology | Purpose |
|---|---|---|
| UI Framework | React 19 | Component-based dashboard |
| Build Tool | Vite 8 | Dev server, HMR, production bundling |
| Routing | react-router-dom v7 | SPA navigation (Dashboard ↔ Workspace) |
| Map Visualization | react-simple-maps | Zoomable, clickable India choropleth map |
| Graph Visualization | react-force-graph-2d | Force-directed entity correlation graph |
| Charts | Recharts | Donut (risk distribution) + Bar (cluster assessment) |
| Styling | CSS Custom Properties | Government color design system |
| Fonts | Google Fonts | Inter (UI) + JetBrains Mono (code/terminals) |

### Data Generation
| Component | Technology | Purpose |
|---|---|---|
| App Framework | Streamlit | Interactive web UI for data generation |
| Synthetic Data | Faker + NumPy | Realistic wallet addresses, IPs, timestamps |
| Distribution | Pareto / Power-law bias | Realistic normal vs. anomalous ratio |

### Infrastructure
| Component | Technology | Purpose |
|---|---|---|
| Graph Database | Neo4j 5.12.0 (Docker) | Transaction graph storage and traversal |
| Containerization | Docker Compose | Neo4j service orchestration |

---

## Repository Structure

```
chainwatch/
│
├── chainwatch_backend/              # Python FastAPI backend
│   ├── main.py                      # Core API + ML pipeline
│   ├── generator_app.py             # Streamlit data generator
│   ├── anomaly_results.json         # Latest ML output (auto-updated)
│   ├── stats.json                   # Aggregate metrics (auto-updated)
│   ├── NTRO_Report_*.pdf            # Sample generated PDF dossier
│   ├── database/                    # MaxMind .mmdb files (not in repo)
│   │   ├── GeoIP-City.mmdb          # Offline IP → State mapping
│   │   └── GeoIP-ASN.mmdb           # Offline IP → ISP/ASN mapping
│   └── venv/                        # Python virtual environment
│
├── chainwatch_frontend/             # React + Vite frontend
│   ├── src/
│   │   ├── App.jsx                  # Root component + SPA routing
│   │   ├── Home.jsx                 # Executive dashboard (main view)
│   │   ├── Workspace.jsx            # Analyst workspace (ingest + isolate)
│   │   ├── india.json               # India GeoJSON for map rendering
│   │   ├── mapUtils.js              # State coordinate lookup + dot generation
│   │   ├── index.css                # Full design system + all component styles
│   │   └── components/
│   │       ├── MetricCards.jsx      # Top-level KPI cards
│   │       ├── AlertTable.jsx       # Threat watchlist with selection
│   │       ├── GraphView.jsx        # Force-directed graph (Neo4j data)
│   │       └── ChartsView.jsx       # Recharts donut + bar charts
│   ├── public/
│   │   ├── favicon.svg
│   │   └── blockchain.png
│   ├── index.html                   # HTML entry point (loads Google Fonts)
│   ├── vite.config.js               # Vite config (port 5173, auto-open)
│   ├── package.json                 # npm dependencies and scripts
│   ├── tsconfig.json                # TypeScript config (type-check only)
│   └── FRONTEND_DOCUMENTATION.md   # Detailed frontend reference
│
├── docker-compose.yml               # Neo4j 5.12 container definition
├── india.geojson                    # India boundary data (root copy)
├── .gitignore
└── README.md                        # This file
```

---

## ML Pipeline Deep Dive

### Why Augmented Synthetic Data?

Pure `np.random` uniform distributions produce data where every wallet looks equally random — an ML model cannot find anomalies because *everything* looks like one. Real financial fraud follows **Power Laws (Pareto distributions)**: the vast majority of transactions are normal retail activity, while a small fraction are high-volume, high-frequency, multi-IP threat actors.

The generator deliberately injects "clustered noise" by forcing specific wallets to transact rapidly across high-risk IPs, giving the ML model a true mathematical signal to detect.

### Stage 1 — Feature Engineering

For every wallet address in the ingested CSV, three features are computed:

| Feature | Description |
|---|---|
| `tx_count` | Number of transactions attributed to this wallet |
| `total_volume_btc` | Cumulative BTC moved by this wallet |
| `unique_ip_count` | Number of distinct source IPs used |

All features are normalized with `StandardScaler` before being fed to the models.

### Stage 2 — Isolation Forest (Anomaly Detection)

```python
IsolationForest(n_estimators=200, contamination=0.10, random_state=42)
```

- Builds 200 random decision trees over the feature space
- Normal wallets require many splits to isolate (high path length → low anomaly score)
- Anomalous wallets (extreme `tx_count`, `volume`, or `unique_ip_count`) are isolated in very few splits (short path length → flagged as anomaly)
- The `contamination=0.10` parameter tells the model to expect ~10% of wallets to be anomalous
- Raw `decision_function` scores are mapped to a human-readable confidence range of **60% – 99%**

### Stage 3 — K-Means Clustering (Behavioral Grouping)

```python
KMeans(n_clusters=min(6, len(wallets)), random_state=42, n_init=10)
```

- Groups flagged wallets into up to **6 behavioral clusters**
- Each cluster maps to a named threat pattern (see [Threat Classification Model](#threat-classification-model))
- Helps analysts understand *how* a wallet is suspicious, not just *that* it is

### Stage 4 — GeoIP & ASN Attribution

For each source IP in the ledger:

1. **Primary lookup:** MaxMind `GeoIP-City.mmdb` → Indian state name
2. **Fallback:** `geo_state` column from the CSV itself
3. **ASN lookup:** MaxMind `GeoIP-ASN.mmdb` → ASN number + organization name

The most frequent state/ASN/ISP per wallet is stored as its `primary_state`, `asn`, and `isp`.

### Output

Results are persisted to two JSON files that the React dashboard reads:

- `anomaly_results.json` — full list of flagged wallets, sorted by confidence score descending
- `stats.json` — aggregate counts: `total_transactions`, `total_wallets`, `anomalies_detected`

---

## API Reference

Base URL: `http://localhost:8000`

### `GET /`
Health check.
```json
{ "status": "ChainWatch Engine Active" }
```

---

### `GET /api/v1/stats`
Returns aggregate pipeline statistics.

**Response:**
```json
{
  "total_transactions": 1000,
  "total_wallets": 150,
  "anomalies_detected": 15
}
```

---

### `GET /api/v1/anomalies`
Returns all flagged wallet anomalies, sorted by confidence score.

**Response:** Array of `AnomalyAlert` objects:
```json
[
  {
    "wallet_address": "538686248209869f83e798641ab5c797e0",
    "confidence_score": 99.0,
    "cluster_id": 2,
    "cluster_name": "Multi-Hop Relay Cluster",
    "reason": "AI detected 62 rapid TXNs masking 1408.48 BTC across 37 distinct IPs.",
    "tx_count": 62,
    "total_volume_btc": 1408.4769,
    "unique_ip_count": 37,
    "primary_state": "Manipur",
    "asn": "AS45609",
    "isp": "Bharti Airtel"
  }
]
```

---

### `POST /api/v1/ingest`
Accepts a raw CSV ledger file, runs the full ML pipeline, and updates `anomaly_results.json` and `stats.json`.

**Request:** `multipart/form-data` with field `file` (CSV)

**Expected CSV columns:**
| Column | Type | Description |
|---|---|---|
| `timestamp` | ISO datetime | Transaction timestamp |
| `src_ip` | IPv4 | Source IP address |
| `dst_ip` | IPv4 | Destination IP address |
| `src_port` | int | Source port |
| `dst_port` | int | Destination port (typically 8333) |
| `txid` | hex string | Transaction ID |
| `input_addresses` | Python list string | Sender wallet addresses |
| `output_addresses` | Python list string | Receiver wallet addresses |
| `input_amounts` | Python list string | BTC amounts per input |
| `output_amounts` | Python list string | BTC amounts per output |
| `geo_state` | string | Fallback state if GeoIP fails |

**Response:**
```json
{
  "message": "Ingestion and ML Analysis Complete",
  "anomalies_found": 15
}
```

---

### `GET /api/v1/report/{wallet_id}`
Generates and streams an NTRO-classified PDF intelligence dossier for the specified wallet address.

**Parameters:**
- `wallet_id` — full wallet address string

**Response:** `application/pdf` — streamed directly to browser

**PDF Contents:**
- Header: "Government of India | NTRO — CLASSIFIED: THREAT INTELLIGENCE DOSSIER"
- Target entity (wallet address)
- AI confidence score
- Behavioral classification (cluster name)
- Geographic jurisdiction (primary operating state)
- ISP / ASN network footprint
- AI evidence log (reason string)
- Generation timestamp
- Official Secrets Act disclaimer

---

## Frontend Application

The React frontend has two main routes:

### `/` — Executive Dashboard (`Home.jsx`)

The command-and-control view for senior analysts and executives.

| Section | Description |
|---|---|
| **Top bar** | NTRO branding, system title, `SECURED — FULLY OFFLINE` status badge, "Ingest New Ledger" CTA |
| **Live Threat Banner** | Red full-width banner triggered on anomaly isolation (double-click the NTRO logo to simulate) |
| **Hero Section** | Full-width banner with mission statement |
| **Threat Ticker** | Auto-scrolling horizontal feed of flagged wallets; pauses when a live threat is detected |
| **Metric Cards** | Transactions Analyzed · Unique Wallets · Threats Isolated |
| **Regional Threat Map** | Clickable India map; click a state to zoom and filter the alert panel |
| **Threat Watchlist** | File-card style alert list; click to select and highlight |
| **Footer** | About, Quick Links, NTRO contact details, copyright |

### `/workspace` — Analyst Workspace (`Workspace.jsx`)

The hands-on analyst interface for ingesting and investigating data.

| Pane | Description |
|---|---|
| **1. Data Ingestion** (left) | File picker + "RUN AI PIPELINE" button; shows file name on selection |
| **2. Geospatial Isolation** (center top) | Interactive map; click state to filter; top anomaly states overlay |
| **Engine Logs** (center bottom) | Terminal-style log stream with color-coded `[ENGINE]`, `[AI]`, `[SUCCESS]`, `[ERROR]` entries |
| **3. Regional Suspects** (right) | Filtered list of flagged wallets for selected state; one-click PDF generation per suspect |

### Component Reference

| Component | File | Description |
|---|---|---|
| `MetricCards` | `components/MetricCards.jsx` | Three KPI stat cards (transactions, wallets, threats) |
| `AlertTable` | `components/AlertTable.jsx` | Scrollable threat file list with selection state |
| `GraphView` | `components/GraphView.jsx` | Force-directed graph: IP → TX → Wallet relationships |
| `ChartsView` | `components/ChartsView.jsx` | Donut chart (risk distribution) + bar chart (cluster breakdown) |

### GraphView Node & Link Types

**Node Types:**
| Type | Normal Color | Flagged Color |
|---|---|---|
| `ip` | Navy `#003366` | Red `#cc0000` |
| `transaction` | Gray `#6b7280` | Light Gray `#9ca3af` |
| `wallet` | Green `#138808` | Saffron `#FF9933` |

**Link Types:**
| Type | Color | Meaning |
|---|---|---|
| `BROADCASTED` | Blue (0.3 opacity) | IP node broadcast a transaction |
| `SENT_TO_NODE` | Light Blue (0.15) | Transaction sent to a node |
| `INPUT_TO_TX` | Teal (0.35) | Wallet input to transaction |
| `OUTPUT_TO_WALLET` | Purple (0.35) | Transaction output to wallet |

### Map Utilities (`mapUtils.js`)

- `STATE_COORDS` — lookup table of `[longitude, latitude]` center coordinates for 14 key Indian states/UTs
- `generateStateDots(stateName, count, geoJson)` — generates `count` random points geometrically inside the state's GeoJSON polygon using ray-casting, for scatter-plot visualization

---

## Data Generator

The Streamlit app (`generator_app.py`) provides an interactive UI for generating realistic synthetic Bitcoin ledger data.

### How it Works

1. **State selection** — Pick a target state index (1–36) to plant a high-confidence threat anomaly in that jurisdiction
2. **Data generation** — Creates 1,000 transactions with the following distribution:
   - **~95% normal traffic** — Pareto-distributed retail transactions, random Indian states, low BTC volumes (0.01–1.5× multiplier)
   - **~5% planted anomalies** — Concentrated in the target state, using 3 specific "threat wallets", high BTC volumes (10–50× multiplier)
3. **Download** — Export as `ledger.csv` for upload into the ChainWatch Workspace

### Running the Generator

```bash
cd chainwatch_backend
source venv/bin/activate
streamlit run generator_app.py
```

Opens at `http://localhost:8501`

### CSV Schema Generated

```
timestamp, src_ip, dst_ip, src_port, dst_port, txid,
input_addresses, output_addresses, input_amounts, output_amounts, geo_state
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Docker Desktop (for Neo4j, optional)
- MaxMind GeoIP databases (`.mmdb` files) — place in `chainwatch_backend/database/`

### Backend Setup

```bash
# Navigate to backend directory
cd chainwatch_backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install fastapi uvicorn pandas numpy scikit-learn maxminddb weasyprint pydantic

# Start the API server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be live at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

> **Note:** If `GeoIP-City.mmdb` and `GeoIP-ASN.mmdb` are not present in `chainwatch_backend/database/`, the engine will fall back to the `geo_state` column in the CSV for state attribution, and ASN/ISP fields will show `N/A`.

### Frontend Setup

```bash
# Navigate to frontend directory
cd chainwatch_frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Opens automatically at `http://localhost:5173`.

### Data Generator Setup

```bash
# From the backend directory with venv active
pip install streamlit faker

streamlit run generator_app.py
```

Opens at `http://localhost:8501`.

### Neo4j (Optional)

```bash
# From the project root
docker-compose up -d
```

- Neo4j Browser: `http://localhost:7474`
- Bolt connection: `bolt://localhost:7687`
- Credentials: `neo4j` / `hackathon2026`

---

## Workflow Guide

This is the end-to-end analyst workflow:

```
Step 1  ─▶  Open the Streamlit Generator (localhost:8501)
            Select a target state index (e.g. 21 = Maharashtra)
            Click "Generate 1,000 Transactions"
            Download ledger.csv

Step 2  ─▶  Open the Analyst Workspace (localhost:5173/workspace)
            Click "Select CSV Ledger" → choose ledger.csv
            Click "RUN AI PIPELINE"
            Watch the engine logs stream in real time:
              [ENGINE] Parsing CSV and extracting network graphs...
              [ENGINE] Resolving GeoIPs and ASN footprints...
              [AI] Running Isolation Forest across 10,000 vectors...
              [AI] Executing K-Means behavioral clustering...
              [SUCCESS] Analysis complete. Found N threats.

Step 3  ─▶  Review Regional Suspects (right pane)
            Click a state on the map to filter by jurisdiction
            Review flagged wallets: volume, ISP, confidence score
            Click "📄 Generate PDF" to produce an NTRO dossier

Step 4  ─▶  Navigate to Executive Dashboard (localhost:5173)
            Review live threat ticker and metric cards
            Click any Indian state on the map to filter the Threat Watchlist
            The Threat Watchlist shows all flagged wallets for that state
```

---

## Threat Classification Model

When K-Means clustering groups the anomalous wallets, each cluster is assigned a named threat pattern:

| Cluster ID | Name | Description |
|---|---|---|
| 0 | **Micro-Transactor Ring** | Many small transactions to avoid detection thresholds |
| 1 | **High-Volume Laundering Node** | Extremely large BTC volumes moved through a single wallet |
| 2 | **Multi-Hop Relay Cluster** | Transactions routed through multiple intermediate wallets ("peeling chains") |
| 3 | **Dormant-then-Active** | Long periods of inactivity followed by sudden burst activity |
| 4 | **Cross-Border Cell** | Activity spanning multiple geographic jurisdictions and ISPs |
| 5 | **Retail Node** | Baseline normal-adjacent behavior; lowest risk cluster |

---

## PDF Intelligence Reports

Each report is generated dynamically by the FastAPI backend using **WeasyPrint** (HTML-to-PDF renderer) and streamed to the browser.

**Report Sections:**
1. **Header** — "Government of India | NTRO" with tricolor border
2. **Date Generated** — Timestamp of report creation
3. **Target Entity** — Full wallet address
4. **AI Confidence Score** — Percentage displayed in red
5. **Behavioral Classification** — K-Means cluster name
6. **Geographical & Network Footprint** — Primary operating state + ISP/ASN
7. **AI Evidence Log** — Natural language description (e.g., *"AI detected 62 rapid TXNs masking 1408.48 BTC across 37 distinct IPs."*)
8. **Footer** — "Generated by ChainWatch Core Engine. Document is subject to Official Secrets Act."

**Sample trigger:** `GET http://localhost:8000/api/v1/report/538686248209869f83e798641ab5c797e0`

---

## Docker & Infrastructure

The `docker-compose.yml` provisions a Neo4j graph database for future transaction graph storage and traversal:

```yaml
services:
  neo4j:
    image: neo4j:5.12.0
    ports:
      - "7474:7474"   # Browser UI
      - "7687:7687"   # Bolt protocol
    environment:
      - NEO4J_AUTH=neo4j/hackathon2026
    volumes:
      - ./neo4j_data:/data
```

**Why Neo4j over SQL for blockchain analysis?**

Tracing money through a "peeling chain" (e.g., 50 wallet hops) requires expensive recursive `JOIN` operations in SQL that can take minutes and crash servers. Neo4j stores relationships natively as first-class citizens. A 10-hop traversal query takes milliseconds in Cypher vs. minutes in SQL.

---

## Sample Data Output

Sample from `anomaly_results.json` after a typical pipeline run:

```json
[
  {
    "wallet_address": "538686248209869f83e798641ab5c797e0",
    "confidence_score": 99.0,
    "cluster_id": 2,
    "cluster_name": "Multi-Hop Relay Cluster",
    "reason": "AI detected 62 rapid TXNs masking 1408.48 BTC across 37 distinct IPs.",
    "tx_count": 62,
    "total_volume_btc": 1408.4769,
    "unique_ip_count": 37,
    "primary_state": "Manipur",
    "asn": "N/A",
    "isp": "N/A"
  },
  {
    "wallet_address": "1938e412ac1f881adc34e7e8cca6ca6e33",
    "confidence_score": 96.9,
    "cluster_id": 2,
    "cluster_name": "Multi-Hop Relay Cluster",
    "reason": "AI detected 66 rapid TXNs masking 1639.63 BTC across 32 distinct IPs.",
    "tx_count": 66,
    "total_volume_btc": 1639.63,
    "unique_ip_count": 32,
    "primary_state": "Manipur",
    "asn": "N/A",
    "isp": "N/A"
  }
]
```

`stats.json` after the same run:

```json
{
  "total_transactions": 1000,
  "total_wallets": 150,
  "anomalies_detected": 15
}
```

---

## Known Limitations & Future Roadmap

### Current Limitations

- **Offline GeoIP accuracy** — MaxMind `.mmdb` files must be sourced and placed manually. Without them, state attribution falls back to the CSV's `geo_state` column, and ISP/ASN fields show `N/A`.
- **No real-time ingestion** — The pipeline is batch-only. Data must be manually uploaded per session; results do not persist across browser refreshes (served from static JSON files).
- **Neo4j not yet wired to frontend** — The graph database is provisioned via Docker but the FastAPI `/graph` endpoint and `GraphView` component are not yet connected in the current build.
- **No authentication** — The API has CORS set to `allow_origins=["*"]`; not suitable for production deployment without auth middleware.
- **Synthetic data only** — No real Bitcoin ledger data is processed. The generator simulates realistic but entirely fictional transactions.

### Roadmap

- [ ] Real-time WebSocket ingestion for live Bitcoin mempool monitoring
- [ ] Neo4j integration — persist transaction graphs; expose `/api/v1/graph` for `GraphView`
- [ ] Advanced filtering in the dashboard (date ranges, BTC volume thresholds, cluster filters)
- [ ] Role-based access control (RBAC) with JWT authentication
- [ ] Dark mode theme
- [ ] Multi-language support (Hindi + regional languages)
- [ ] Alert export (bulk CSV / PDF batch download)
- [ ] Keyboard accessibility and WCAG 2.1 AA compliance audit
- [ ] Automated test suite (pytest for backend, Vitest for frontend)
- [ ] Deployment packaging (Dockerfile for FastAPI backend)

---

<div align="center">

**ChainWatch Core Engine** · Built for NTRO · Government of India

*Block-III, Old JNU Campus, New Delhi — 110067*  
`cyber-intel@ntro.gov.in`

© 2026 National Technical Research Organisation, Government of India. All rights reserved.  
*This document is subject to the Official Secrets Act.*

</div>
