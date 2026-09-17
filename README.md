# ChainWatch — National Crypto-Threat Intelligence Network

> **NTRO Proof of Concept** · Advanced AI & Graph-Driven Blockchain Forensics Platform for Detecting Laundering Sequences, Peeling Chains, and Threat Activity Across Indian Jurisdictions.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Capabilities & Forensic Engines](#2-key-capabilities--forensic-engines)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Repository Structure](#5-repository-structure)
6. [Forensic Subsystems](#6-forensic-subsystems)
   - [Neo4j Idempotent MERGE Graph Engine](#61-neo4j-idempotent-merge-graph-engine)
   - [Peeling-Chain & CoinJoin Detector](#62-peeling-chain--coinjoin-detector)
   - [Exponential Decay Risk Propagation](#63-exponential-decay-risk-propagation)
   - [Broadcast IP Time Correlation](#64-broadcast-ip-time-correlation)
7. [REST API Reference](#7-rest-api-reference)
8. [Setup & Installation](#8-setup--installation)
9. [Running the Application](#9-running-the-application)
10. [Stopping the Application](#10-stopping-the-application)
11. [PDF Dossier Generation](#11-pdf-dossier-generation)

---

## 1. Project Overview

**ChainWatch** is an offline intelligence platform built as a National Technical Research Organisation (NTRO) proof-of-concept. It ingests cryptocurrency transaction ledgers, executes multi-stage unsupervised machine learning and graph analytics, enriches transaction records with geolocation & ASN footprints, and visualizes threats across an interactive React dashboard and Neo4j graph network.

---

## 2. Key Capabilities & Forensic Engines

- **Neo4j Aura Cloud Integration:** High-performance transactional graph database storage utilizing Cypher `UNWIND` batch `MERGE` queries to guarantee 100% idempotent writes.
- **Peeling Chain Detection:** Identifies automated laundering sequences where large funds (e.g. 50 BTC) are split into small cashout peels ($< 15\%$) and change relays ($> 85\%$) over $\ge 3$ consecutive transaction hops.
- **CoinJoin / Mixing Protocol Detection:** Flags obfuscated multi-party mixing transactions with uniform output amounts.
- **Decay-Based Risk Score Propagation:** Computes risk scores for downstream recipient wallets reachable from seed threats ($R(w) = \max R(s) \cdot 0.70^d$).
- **Exponential Decay Broadcast IP Correlation:** Scores candidate transaction broadcaster IPs ($c = e^{-\Delta t / \tau}$) relative to earliest capture timestamp ($\tau = 8.0\text{s}$).
- **Interactive Geospatial & Neural Topology Visualization:** Choropleth-style map of India with threat dot markers, connected transaction inspectors, and 2D force-directed graph rendering.
- **Automated State Reset & Database Wipe:** Automatically clears old run data prior to new dataset ingestion, with on-demand `/api/v1/clear` API endpoint and UI reset controls.
- **One-Click Official PDF Dossier Generation:** Generates RESTRICTED NTRO Threat Intelligence Reports styled for government agency distribution.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER BROWSER                                      │
│                                                                             │
│   ┌─────────────────────────────┐         ┌─────────────────────────────┐   │
│   │    React 19 + Vite          │         │    Streamlit Generator      │   │
│   │    (port 5173)              │         │    (port 8501)              │   │
│   │                             │         │                             │   │
│   │  Executive Dashboard        │         │  Synthetic ledger UI        │   │
│   │  Analyst Workspace          │         │  → downloads ledger.csv     │   │
│   └──────────────┬──────────────┘         └─────────────────────────────┘   │
│                  │ REST API / HTTP                                          │
└──────────────────┼──────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│    FastAPI Core Engine (port 8000)                                          │
│                                                                             │
│    POST /api/v1/ingest           ← Receives ledger.csv                      │
│      ├─ GeoIP & ASN Resolution   ← MaxMind MMDB + CSV Range Fallback        │
│      ├─ IP Broadcast Correlation ← Exponential Decay Scoring (tau = 8.0s)   │
│      ├─ Unsupervised ML          ← Isolation Forest + K-Means               │
│      ├─ Peeling-Chain Engine     ← Multi-Hop Split Sequence Tracing          │
│      ├─ CoinJoin Mixing Engine   ← Uniform Output Variance Detection        │
│      ├─ Risk Propagation         ← Decay Propagation (0.70^d)                │
│      └─ Neo4j Batch Writes       ← Idempotent UNWIND MERGE Cypher           │
│                                                                             │
│    GET  /api/v1/anomalies        ← Serves anomaly results & risk factors    │
│    GET  /api/v1/graph            ← Serves graph nodes, links & peeling chains│
│    GET  /api/v1/stats            ← Serves system metrics & wallet dots      │
│    POST /api/v1/clear            ← Wipes Neo4j database & workspace state   │
│    GET  /api/v1/report/{id}      ← Generates & streams PDF dossier          │
└──────────────────┬──────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│    Neo4j Graph Database (Neo4j Aura Cloud / Local Docker port 7687)         │
│    Nodes: (:Wallet), (:Transaction), (:IP)                                  │
│    Edges: (:SENT), (:RECEIVED_BY), (:BROADCAST), (:SAME_ENTITY_AS)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

- **Backend:** Python 3.10+, FastAPI, PyDantic Settings, Neo4j Python Driver, Scikit-learn, Pandas, NumPy, NetworkX, MaxMindDB, WeasyPrint.
- **Frontend:** React 19, Vite, React Router DOM v7, React Simple Maps, React Force Graph 2D, Recharts.
- **Data Generator:** Streamlit, Faker, Pandas.
- **Database:** Neo4j 5.x (Aura Cloud / Docker container).

---

## 5. Repository Structure

```
chainwatch/
├── Start.sh                           # Unified parallel launcher (Backend, Streamlit, Frontend)
├── Kill.sh                            # Process group teardown script
├── docker-compose.yml                 # Local Neo4j container definition
├── .gitignore                         # Configured to ignore secrets, logs, pycache, pdfs, and json state
├── IP_Address.csv                     # Offline IP range lookup reference
├── dbip-asn-lite-2026-09.csv          # Offline ASN range lookup reference
├── india.geojson                      # GeoJSON bounds for map of India
├── chainwatch_backend/
│   ├── .env                           # Environment configuration (secrets ignored)
│   ├── .env.example                   # Environment template
│   ├── requirements.txt               # Backend Python dependencies
│   ├── config.py                      # Pydantic Settings & path resolver
│   ├── main.py                        # FastAPI application endpoints
│   ├── generator_app.py               # Streamlit synthetic data generator
│   ├── db/
│   │   ├── neo4j_driver.py            # Singleton Neo4j driver & session wrapper
│   │   └── queries.py                 # UNWIND batch MERGE Cypher queries
│   ├── analytics/
│   │   ├── correlation.py             # IP broadcast exponential decay correlation
│   │   ├── peeling_chain.py           # Peeling chain & CoinJoin mixing detector
│   │   └── risk_propagation.py        # Decay-based Risk Propagation engine
│   ├── services/
│   │   ├── geoip.py                   # MaxMind MMDB + CSV range resolver
│   │   └── graph_builder.py           # Ingest orchestrator & batch graph builder
│   └── tests/
│       ├── test_neo4j_connection.py   # Neo4j connectivity unit test
│       └── test_analytics.py          # Forensic detection unit tests
└── chainwatch_frontend/
    ├── package.json                   # Frontend dependencies
    ├── index.html                     # Entry point HTML
    └── src/
        ├── App.jsx                    # React Router configuration
        ├── Home.jsx                   # Executive Dashboard view
        ├── Workspace.jsx              # Analyst Workspace view
        ├── mapUtils.js                # Geospatial dot calculation utilities
        └── components/
            ├── GraphView.jsx          # 2D Force-Directed Neural Map
            ├── AlertTable.jsx         # Risk-badged threat table
            ├── ChartsView.jsx         # Bar & pie charts for cluster/volume analytics
            └── MetricCards.jsx        # Forensic metrics summary cards
```

---

## 6. Forensic Subsystems

### 6.1 Neo4j Idempotent MERGE Graph Engine
All graph modifications use Cypher `MERGE` logic executed in batches via `UNWIND`. Re-ingesting the same ledger or overlapping transactions updates node attributes (such as risk score and broadcast confidence) without generating duplicate edges.

### 6.2 Peeling-Chain & CoinJoin Detector
- **Peeling Chain:** Traces directed transaction sequences $T_1 \to W_{c1} \to T_2 \to W_{c2} \dots \to T_k$ (depth $\ge 3$) where change volume $> 85\%$ and peel volume $< 15\%$.
- **CoinJoin Mixing:** Detects multi-input ($\ge 3$), multi-output ($\ge 3$) transactions with uniform output amounts ($< 2\%$ variance).

### 6.3 Exponential Decay Risk Propagation
Seed threat wallets (flagged by Isolation Forest, Peeling Chains, or CoinJoin mixers) are assigned an initial Risk Score $R(s) = 95\text{--}100$. Risk propagates to downstream wallets using:
$$R(w) = \max_{s \in S} \left( R(s) \cdot 0.70^{d(s, w)} \right)$$

### 6.4 Broadcast IP Time Correlation
Candidate broadcaster IPs for a transaction are evaluated relative to the earliest observed capture timestamp:
$$\text{confidence} = e^{-\Delta t / \tau}, \quad \tau = 8.0\text{s}$$
Captures outside $\Delta t > 30\text{s}$ are dropped as network relay noise.

---

## 7. REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | System health check & active forensic capabilities |
| `/api/v1/stats` | `GET` | System metrics, anomalies count, peeling chains count, and wallet location dots |
| `/api/v1/anomalies` | `GET` | List of isolated threat wallets with confidence & risk scores |
| `/api/v1/graph` | `GET` | Full neural graph topology (nodes, links, peeling chains, mixers) |
| `/api/v1/peeling-chains` | `GET` | List of detected peeling chain laundering sequences |
| `/api/v1/mixers` | `GET` | List of detected CoinJoin mixing transactions |
| `/api/v1/ingest` | `POST` | Upload `ledger.csv`, wipe old state, run ML pipeline, and write to Neo4j |
| `/api/v1/clear` | `POST` / `DELETE` | Wipes Neo4j database (`MATCH (n) DETACH DELETE n`) and resets JSON state |
| `/api/v1/report/{wallet_id}` | `GET` | Generates and streams an official NTRO PDF Threat Dossier |

---

## 8. Setup & Installation

### 1. Backend Environment Setup
```bash
cd chainwatch_backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your Neo4j credentials:
```bash
cp .env.example .env
```
Edit `.env`:
```env
NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
NEO4J_DATABASE=neo4j
```

### 3. Frontend Setup
```bash
cd ../chainwatch_frontend
npm install
```

---

## 9. Running the Application

Launch all services in parallel using the unified startup script:
```bash
./Start.sh
```

This starts:
1. **FastAPI Backend Core Engine** at `http://localhost:8000`
2. **Streamlit Synthetic Data Generator** at `http://localhost:8501`
3. **React Executive Dashboard** at `http://localhost:5173`

---

## 10. Stopping the Application

To tear down all process groups and clean up background tasks:
```bash
./Kill.sh
```

---

## 11. PDF Dossier Generation

Accessing `/api/v1/report/{wallet_id}` dynamically compiles an official government-styled HTML template into a PDF using `WeasyPrint`, featuring:
- Official NTRO & Cyber Intelligence Division classification header
- Subject identification & behavioural cluster classification
- Propagated risk assessment score & risk factors breakdown
- Autonomous System (ASN) and IP footprint
- Analytical evidence log & handling notices
