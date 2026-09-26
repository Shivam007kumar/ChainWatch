# ChainWatch — National Crypto-Threat Intelligence Network

> **NTRO Proof of Concept** · Offline Bitcoin Forensic Intelligence Platform for Detecting Laundering Sequences, Peeling Chains, CoinJoin Mixing, and Threat Activity Across Indian Jurisdictions.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [End-to-End Process Flow](#2-end-to-end-process-flow)
3. [Key Capabilities](#3-key-capabilities)
4. [System Architecture](#4-system-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Repository Structure](#6-repository-structure)
7. [Forensic Subsystems](#7-forensic-subsystems)
8. [REST API Reference](#8-rest-api-reference)
9. [Setup & Installation](#9-setup--installation)
10. [Running the Application](#10-running-the-application)
11. [Stopping the Application](#11-stopping-the-application)
12. [Running Tests](#12-running-tests)
13. [Dashboard Walkthrough](#13-dashboard-walkthrough)

---

## 1. Project Overview

**ChainWatch** is a fully offline Bitcoin transaction intelligence platform built as an NTRO proof-of-concept. It accepts raw cryptocurrency transaction ledgers (CSV), runs a multi-stage unsupervised ML and graph-analytics pipeline entirely on-premises, enriches every record with GeoIP and ASN data, persists the complete intelligence graph to a local Neo4j instance, and exposes the results through a React 19 dashboard and a set of frozen investigation REST APIs.

No cloud accounts, no external API calls, no synthetic numbers — every metric on the dashboard is derived from real Neo4j queries against the ingested data.

**Verified on 10,000-row dataset:**

| Metric | Value |
|---|---|
| Transactions | 10,000 |
| Wallet entities | 2,265 |
| IP endpoints | 18,573 |
| Anomalies (IsolationForest) | 227 |
| Peeling chains detected | 5 |
| CoinJoin mixers detected | 10 |
| Propagated risk wallets | 2,265 |
| Integration tests | 22 / 22 pass |

---

## 2. End-to-End Process Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1 — DATA GENERATION                                                    │
│                                                                              │
│  Streamlit Generator  (port 8501)                                            │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  User selects: row count · target state · seed · anomaly scenarios     │  │
│  │                                                                        │  │
│  │  Generator plants deterministic anomaly patterns:                      │  │
│  │    • Peeling chains  (exact 80/20 split sequences, ≥ 6 hops)           │  │
│  │    • CoinJoin mixers (4+ inputs, 4 equal outputs, < 2% variance)       │  │
│  │    • High fan-out / fan-in bursts, high-volume, irregular amounts      │  │
│  │                                                                        │  │
│  │  Output: chainwatch_<N>.csv  (ignored by .gitignore)                   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                │                                             │
│                    Download CSV from browser                                 │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 2 — INGESTION  (POST /api/v1/ingest)                                   │
│                                                                              │
│  React Frontend uploads CSV → FastAPI validates & parses every row           │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Validator (ingestion/validator.py)                                    │  │
│  │    • Schema check (required columns, types, JSON arrays)               │  │
│  │    • txid format validation (regex: [a-zA-Z0-9_\-]{1,80})              │  │
│  │    • Skips malformed rows, reports skipped count                       │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 3 — GEOIP & ASN ENRICHMENT  (services/geoip.py)                        │
│                                                                              │
│  For every src_ip and dst_ip in the dataset:                                 │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  1. MaxMind GeoLite2-City.mmdb  → city / state / country              │  │
│  │  2. MaxMind GeoLite2-ASN.mmdb   → ASN number + organization           │  │
│  │  3. IP_Address.csv fallback     → Indian state range lookup            │  │
│  │                                                                        │  │
│  │  Output fields per IP: city, state, country, asn, organization        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 4 — BROADCAST IP CORRELATION  (analytics/correlation.py)               │
│                                                                              │
│  Groups transaction captures by txid. For each (txid, ip) pair:             │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  confidence = exp(−Δt / τ)   where τ = 8.0 s                          │  │
│  │                                                                        │  │
│  │  • Δt = seconds since earliest observed capture for that txid          │  │
│  │  • Captures with Δt > 30s are dropped as relay noise                  │  │
│  │  • Highest-confidence IP is tagged as primary broadcaster              │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 5 — UNSUPERVISED ML PIPELINE  (analytics/)                             │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │  IsolationForest  (anomaly.py)                                      │     │
│  │    14 wallet-level features:                                        │     │
│  │      tx_count, total_volume_btc, avg_tx_btc, unique_counterparties  │     │
│  │      fanout_ratio, fanin_ratio, tx_velocity, fee_ratio_mean         │     │
│  │      output_entropy, btc_round_tx_ratio, unique_src_ips             │     │
│  │      dst_src_state_match, cross_state_ratio, p2sh_ratio             │     │
│  │    contamination = 0.10  →  flags ~10% as anomalous                 │     │
│  │    Output: anomaly_score per wallet, binary anomaly flag            │     │
│  │                                                                     │     │
│  │  K-Means Clustering  (clustering.py)                                │     │
│  │    Clusters wallets into 5 behavioural groups:                      │     │
│  │      High-Volume Relay, Structured Aggregator, Cross-Border Mule    │     │
│  │      Micro-Transaction Disperser, Low-Activity Peer                 │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │  SHAP Explainer  (analytics/shap_explainer.py)                      │     │
│  │    TreeExplainer on the trained IsolationForest model               │     │
│  │    Produces top-3 feature attributions per flagged wallet:          │     │
│  │      shap_value · feature_value · sigma · direction · % contribution│     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │  Peeling Chain Detector  (analytics/peeling_chain.py)               │     │
│  │    Scans for 2-output transactions with ≥ 80/20 split               │     │
│  │    Builds directed change-wallet graph via NetworkX                 │     │
│  │    Finds directed paths of length ≥ 3 hops                         │     │
│  │    Output: chain_id, hop_count, total_peeled_btc, risk_score        │     │
│  │                                                                     │     │
│  │  CoinJoin Detector  (analytics/peeling_chain.py)                    │     │
│  │    Flags txs with ≥ 3 distinct inputs, ≥ 3 outputs,                │     │
│  │    uniform output amounts (< 2% variance)                           │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐     │
│  │  Risk Propagation  (analytics/risk_propagation.py)                  │     │
│  │    Seed threats: IsolationForest anomalies + peeling + coinjoin     │     │
│  │    CIOU (co-IP observed-usage) risk merging from IP correlation     │     │
│  │    BFS from each seed through SENT/RECEIVED_BY graph edges          │     │
│  │    R(w) = max_s( R(s) × 0.70^d(s,w) )                              │     │
│  │    Output: propagated risk score + distance per wallet              │     │
│  └─────────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 6 — NEO4J GRAPH PERSISTENCE  (services/graph_builder.py)               │
│                                                                              │
│  All writes use Cypher MERGE (idempotent — safe to re-ingest same data):     │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  Node types:                                                           │  │
│  │    (:Dataset {dataset_id, row_count, created_at})                     │  │
│  │    (:Wallet  {address, risk_score, cluster, state, flagged, …})       │  │
│  │    (:Transaction {txid, timestamp, fee_btc, script_type, …})          │  │
│  │    (:IP {address, state, asn, organization})                          │  │
│  │    (:Alert  {alert_id, detector, severity, risk_score, evidence, …})  │  │
│  │                                                                        │  │
│  │  Relationship types:                                                   │  │
│  │    (Wallet)-[:SENT {amount_btc}]->(Transaction)                       │  │
│  │    (Transaction)-[:RECEIVED_BY {amount_btc}]->(Wallet)                │  │
│  │    (Transaction)-[:BROADCAST {confidence}]->(IP)                      │  │
│  │    (Transaction)-[:OBSERVED_DESTINATION]->(IP)                        │  │
│  │    (Wallet)-[:BELONGS_TO_DATASET]->(Dataset)                          │  │
│  │    (Alert)-[:ABOUT]->(Wallet)                                         │  │
│  │                                                                        │  │
│  │  Schema: 5 uniqueness constraints + 10 indexes (db/schema.py)         │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  Ingest response (synchronous):                                              │
│    { message, dataset_id, anomalies_found, peeling_chains_found,            │
│      coinjoin_mixers_found, propagated_risk_wallets,                        │
│      rows_skipped, graph_transaction_count, total_transaction_count }       │
└────────────────────────────────┼─────────────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 7 — REACT DASHBOARD & INVESTIGATION APIs                               │
│                                                                              │
│  React 19 frontend (port 5173) reads live Neo4j data via FastAPI:            │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  /              → Landing Page (system intro, CTAs)                    │  │
│  │  /dashboard     → Executive Dashboard                                  │  │
│  │                     • MetricCards  (txs, wallets, threats, chains)     │  │
│  │                     • Choropleth threat map of India                   │  │
│  │                     • Risk distribution chart                          │  │
│  │                     • AI cluster chart (K-Means groups)                │  │
│  │                     • Live ticker                                      │  │
│  │                                                                        │  │
│  │  /investigate/:address → Neural Map Workstation                        │  │
│  │                     • Wallet/transaction/IP inspector                  │  │
│  │                     • Force-directed graph (hops, direction controls)  │  │
│  │                     • SHAP attribution panel                           │  │
│  │                     • Timeline view                                    │  │
│  │                     • Multi-branch investigation tracking              │  │
│  │                                                                        │  │
│  │  /alerts        → Paginated alert table (filter by detector/severity)  │  │
│  │  /search        → Unified wallet / txid / IP search                   │  │
│  │  /ingest        → CSV upload + real-time ingest progress               │  │
│  │  /about         → Methodology & platform documentation                 │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Key Capabilities

- **Fully offline:** No cloud accounts, no external API calls. All GeoIP, ML, and graph processing runs locally.
- **Idempotent ingestion:** Re-ingesting the same CSV never creates duplicate nodes or alert records (MERGE + dataset isolation).
- **SHAP explainability:** Every flagged wallet has top-3 feature attributions from a TreeExplainer on the trained IsolationForest model.
- **Peeling chain detection:** Detects exact ≥80/20 split sequences with NetworkX path analysis (min 3 hops).
- **CoinJoin mixing detection:** Flags multi-party mixing transactions with uniform denominations (< 2% output variance).
- **Decay-based risk propagation:** BFS from seed threats with `R(w) = R(s) × 0.70^d` — every wallet in the dataset gets a risk score.
- **Frozen investigation APIs:** 17 endpoints covering wallet profile, graph traversal, transaction detail, IP attribution, path finding, alert pagination, and full-text search.
- **Dataset isolation:** Every ingest is tagged with a `dataset_id`; stats and alerts are scoped to the active dataset.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER BROWSER                                   │
│                                                                             │
│  ┌──────────────────────────────┐     ┌───────────────────────────────┐    │
│  │  React 19 + Vite (port 5173) │     │  Streamlit Generator (8501)   │    │
│  │                              │     │                               │    │
│  │  Landing  /                  │     │  Dataset size, seed, state    │    │
│  │  Dashboard  /dashboard       │     │  Anomaly toggles              │    │
│  │  Investigate  /investigate   │     │  → Downloads chainwatch_N.csv │    │
│  │  Alerts  /alerts             │     └───────────────────────────────┘    │
│  │  Search  /search             │                                          │
│  │  Ingest  /ingest             │                                          │
│  │  About  /about               │                                          │
│  └──────────────┬───────────────┘                                          │
│                 │  REST (X-API-Key: chainwatch-local on mutating endpoints) │
└─────────────────┼───────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (port 8000)                                               │
│                                                                             │
│  api/health.py         GET  /api/v1/health/ready                            │
│  api/stats.py          GET  /api/v1/stats                                   │
│  api/alerts.py         GET  /api/v1/alerts                                  │
│  api/search.py         GET  /api/v1/search                                  │
│  api/investigations.py GET  /api/v1/investigations/wallet/{address}         │
│                        GET  /api/v1/investigations/wallet/{address}/graph   │
│                        GET  /api/v1/investigations/wallet/{address}/timeline│
│                        GET  /api/v1/investigations/transaction/{txid}       │
│                        GET  /api/v1/investigations/ip/{ip}                  │
│                        GET  /api/v1/investigations/path                     │
│  ingestion/pipeline.py POST /api/v1/ingest  [X-API-Key]                     │
│  main.py               POST /api/v1/clear   [X-API-Key]                     │
│                                                                             │
│  Pipeline stages (services/graph_builder.py):                               │
│    Validate → GeoIP → Correlate → IsolationForest+SHAP →                   │
│    PeelingChain → CoinJoin → KMeans → RiskPropagation → Neo4j MERGE         │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │  Bolt (port 7687)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Neo4j 5.12.0  (Docker — docker-compose.yml)                                │
│                                                                             │
│  Nodes:  :Dataset  :Wallet  :Transaction  :IP  :Alert                       │
│  Edges:  :SENT  :RECEIVED_BY  :BROADCAST  :OBSERVED_DESTINATION             │
│          :BELONGS_TO_DATASET  :ABOUT                                        │
│                                                                             │
│  5 uniqueness constraints + 10 composite indexes                            │
│  Browser UI → http://localhost:7474                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Backend framework | FastAPI + Uvicorn | 0.115.0 / 0.32.0 |
| Graph database | Neo4j (Docker) + Python driver | 5.12.0 / 5.25.0 |
| ML — anomaly detection | scikit-learn IsolationForest | 1.5.2 |
| ML — clustering | scikit-learn KMeans | 1.5.2 |
| ML — explainability | SHAP TreeExplainer | 0.46.0 |
| Graph analytics | NetworkX | 3.4.2 |
| Data processing | Pandas + NumPy | 2.2.3 / 2.1.2 |
| GeoIP resolution | MaxMindDB + CSV fallback | 2.6.2 |
| Config management | Pydantic Settings | 2.9.2 / 2.5.2 |
| Frontend framework | React + Vite | 19 / 8 |
| Routing | React Router DOM | v7 |
| Geospatial map | React Simple Maps | — |
| Network graph | React Force Graph 2D | — |
| Charts | Recharts | — |
| Data generator | Streamlit | — |
| Runtime | Python | 3.14 |

---

## 6. Repository Structure

```
chainwatch/
├── Start.sh                            # Launches backend + generator + frontend in parallel
├── Kill.sh                             # Tears down all background processes
├── docker-compose.yml                  # Local Neo4j 5.12.0 container
├── .gitignore                          # Excludes .env, venv, GeoIP DBs, CSVs, logs, JSON state
├── IP_Address.csv                      # Indian IP range reference (tracked)
├── india.geojson                       # GeoJSON state boundaries for dashboard map
├── india_city.geojson                  # GeoJSON city boundaries
│
├── chainwatch_backend/
│   ├── .env.example                    # Environment variable template
│   ├── requirements.txt                # All Python dependencies (pinned versions)
│   ├── config.py                       # Pydantic Settings — all tuneable parameters
│   ├── main.py                         # FastAPI app, route registration, CORS, security
│   ├── generator_app.py                # Streamlit dataset generator with planted anomalies
│   │
│   ├── api/                            # Thin route handlers — no business logic
│   │   ├── health.py                   # GET /api/v1/health/ready
│   │   ├── stats.py                    # GET /api/v1/stats
│   │   ├── alerts.py                   # GET /api/v1/alerts (paginated, filterable)
│   │   ├── search.py                   # GET /api/v1/search
│   │   └── investigations.py           # GET /api/v1/investigations/* (6 sub-routes)
│   │
│   ├── ingestion/
│   │   ├── pipeline.py                 # POST /api/v1/ingest orchestration
│   │   ├── validator.py                # Row-level schema + txid regex validation
│   │   └── jobs.py                     # IngestionJob model
│   │
│   ├── analytics/
│   │   ├── anomaly.py                  # IsolationForest — 14 features, contamination=0.10
│   │   ├── clustering.py               # KMeans — 5 behavioural clusters
│   │   ├── correlation.py              # Exponential decay broadcast IP scoring
│   │   ├── peeling_chain.py            # Peeling chain (≥80/20, ≥3 hops) + CoinJoin detector
│   │   ├── risk_propagation.py         # BFS risk decay + CIOU IP-risk merging
│   │   └── shap_explainer.py           # SHAP TreeExplainer, top-3 attributions per wallet
│   │
│   ├── db/
│   │   ├── neo4j_driver.py             # Singleton Neo4j driver + session wrapper
│   │   ├── schema.py                   # Constraint + index creation on startup
│   │   └── queries/
│   │       ├── common.py               # Shared helpers
│   │       ├── wallet.py               # Wallet profile + graph traversal queries
│   │       ├── transaction.py          # Transaction detail queries
│   │       ├── ip.py                   # IP attribution queries
│   │       ├── path.py                 # Shortest path queries
│   │       └── search.py               # Full-text search queries
│   │
│   ├── services/
│   │   ├── geoip.py                    # MaxMind MMDB + CSV range IP resolver
│   │   ├── graph_builder.py            # Full ingest pipeline orchestrator
│   │   ├── evidence.py                 # Evidence package builder per wallet
│   │   └── investigation/
│   │       ├── wallet.py               # Wallet investigation service
│   │       ├── transaction.py          # Transaction investigation service
│   │       ├── ip.py                   # IP investigation service
│   │       └── path.py                 # Path-finding service
│   │
│   ├── models/
│   │   ├── domain/
│   │   │   ├── alert.py                # Alert domain model
│   │   │   ├── transaction.py          # CanonicalTransaction model
│   │   │   └── job.py                  # IngestionJob model
│   │   └── responses/                  # (reserved for response schemas)
│   │
│   └── tests/
│       ├── test_analytics.py           # 9 unit tests — detectors, SHAP, risk
│       ├── test_integration.py         # 13 end-to-end API tests (22/22 pass)
│       ├── test_full_suite.py          # Extended suite (9 pre-existing shape mismatches)
│       └── test_neo4j_connection.py    # Neo4j connectivity check
│
└── chainwatch_frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── App.jsx                     # React Router — 7 routes
        ├── api/                        # Central API client layer
        │   ├── client.js               # fetch wrapper + X-API-Key injection
        │   ├── stats.js
        │   ├── alerts.js
        │   ├── search.js
        │   ├── investigations.js
        │   ├── ingestion.js
        │   └── health.js
        ├── pages/
        │   ├── LandingPage.jsx         # / — system intro + CTAs
        │   ├── DashboardPage.jsx       # /dashboard — metrics, map, charts
        │   ├── InvestigationPage.jsx   # /investigate/:address — Neural Map workstation
        │   ├── AlertsPage.jsx          # /alerts — paginated alert table
        │   ├── SearchPage.jsx          # /search — unified entity search
        │   ├── IngestPage.jsx          # /ingest — CSV upload
        │   └── AboutPage.jsx           # /about — methodology
        └── components/
            ├── CwNav.jsx               # Shared navigation bar
            ├── MetricCards.jsx         # Forensic summary KPI cards
            ├── ChartsView.jsx          # Risk distribution + cluster charts
            ├── InvestigationGraph.jsx  # Force-directed graph (new)
            ├── InspectorPanel.jsx      # Wallet/tx/IP detail panel
            ├── GraphView.jsx           # Legacy graph component (preserved)
            └── AlertTable.jsx          # Risk-badged alert rows
```

---

## 7. Forensic Subsystems

### 7.1 IsolationForest Anomaly Detection

Trains an `IsolationForest(contamination=0.10)` on 14 wallet-level features extracted from the transaction graph. Features capture volume, velocity, fan-out/in, fee behaviour, entropy, cross-state routing, and script-type mixing. Flags approximately 10% of wallets as anomalous; those above a decision threshold receive an `anomaly_score`.

### 7.2 SHAP Explainability

A `shap.TreeExplainer` is fitted on the same IsolationForest model. For every flagged wallet, the top-3 features by absolute SHAP value are returned with `shap_value`, `feature_value`, `sigma` (z-score), `direction` (positive/negative), and `pct_contribution`. These appear in the investigation panel and alert detail view.

### 7.3 Peeling Chain Detector

Scans all transactions for the 2-output pattern where one output carries ≥ 80% of value (change relay) and the other ≤ 20% (cashout peel). Builds a directed `NetworkX` graph of `change_wallet → next_src_wallet` edges, then enumerates simple paths of length ≥ 3 hops. Each detected chain produces a `chain_id`, `hop_count`, `total_peeled_volume_btc`, and a risk score of `70 + 5 × hops` (capped at 95).

### 7.4 CoinJoin Mixing Detector

Flags transactions with ≥ 3 distinct input addresses, ≥ 3 distinct output addresses, and output amounts whose maximum deviation from the mean is < 2% of the mean. These are characteristic of coordinated mixing protocols.

### 7.5 Exponential Decay IP Correlation

For each `txid`, groups all observed `(timestamp, src_ip)` captures. The earliest timestamp becomes `t₀`. Each capture's broadcast confidence is `exp(−Δt / 8.0)`. Captures more than 30 seconds after `t₀` are discarded. The highest-confidence IP becomes the `primary_broadcaster` for the transaction.

### 7.6 Decay Risk Propagation

Seed wallets (from IsolationForest + peeling chains + CoinJoin + CIOU IP merging) receive initial risk scores of 85–100. A BFS traversal from each seed follows `SENT → RECEIVED_BY` edges. Each hop decays the score by `0.70`. A downstream wallet's final score is the maximum across all seed paths: `R(w) = max_s(R(s) × 0.70^d(s,w))`.

### 7.7 Neo4j Idempotent Graph Writes

All writes use Cypher `UNWIND [...] MERGE` batches. Re-ingesting the same dataset updates attributes without creating duplicate nodes or relationships. Alert nodes carry a `dedup_key` (`detector:entity_id:dataset_id`) to prevent duplicate alerts across re-ingests.

---

## 8. REST API Reference

All endpoints are prefixed `/api/v1/`. Endpoints marked `[🔑]` require `X-API-Key: chainwatch-local`.

### System

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health/ready` | Neo4j connectivity + GeoIP MMDB status |
| `POST` | `/clear` 🔑 | Wipe all Neo4j nodes, relationships, and indexes |

### Stats

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/stats` | `{ entities, risk, detections, network }` — all counts from Neo4j |

### Alerts

| Method | Endpoint | Query params | Description |
|---|---|---|---|
| `GET` | `/alerts` | `severity`, `min_risk`, `detector`, `sort`, `order`, `limit`, `offset` | Paginated alert list from Neo4j Alert nodes |

### Search

| Method | Endpoint | Query params | Description |
|---|---|---|---|
| `GET` | `/search` | `q`, `types`, `limit` | Full-text search across wallets, transactions, IPs |

### Investigations

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/investigations/wallet/{address}` | Entity profile, risk, SHAP, evidence, timeline |
| `GET` | `/investigations/wallet/{address}/graph` | Semantic graph (nodes + edges + BTC amounts) |
| `GET` | `/investigations/wallet/{address}/timeline` | Ordered transaction history |
| `GET` | `/investigations/transaction/{txid}` | Inputs, outputs, broadcast IP, destination |
| `GET` | `/investigations/ip/{ip}` | IP geo/ASN, associated transactions |
| `GET` | `/investigations/path` | `source`, `target`, `max_hops`, `strategy=shortest` |

### Ingest

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest` 🔑 | Upload `multipart/form-data` CSV. Synchronous. Returns ingest summary. |

---

## 9. Setup & Installation

### Prerequisites

- Docker Desktop (for Neo4j)
- Python 3.11+ with `venv`
- Node.js 20+ with npm
- GeoIP databases (not in repo — see below)

### 1. Clone and enter the repo

```bash
git clone https://github.com/Shivamkumar/ChainWatch.git
cd chainwatch
```

### 2. Start Neo4j

```bash
docker compose up -d
```

Neo4j will be available at `http://localhost:7474` (Browser) and `bolt://localhost:7687` (driver). Default credentials: `neo4j / chainwatch2026`.

### 3. Backend setup

```bash
cd chainwatch_backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

The defaults in `.env.example` work with the Docker Compose Neo4j out of the box:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=hackathon2026
NEO4J_DATABASE=neo4j
API_KEY=chainwatch-local
```

### 5. GeoIP databases (required for IP enrichment)

Download from [MaxMind](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data) (free account required):

- `GeoLite2-City.mmdb` → place in `GeoLite2-City_<date>/`
- `GeoLite2-ASN.mmdb`  → place in `GeoLite2-ASN_<date>/`

Update paths in `.env` if needed (defaults in `config.py` scan for `GeoLite2-City_*/` and `GeoLite2-ASN_*/` automatically).

### 6. Frontend setup

```bash
cd chainwatch_frontend
npm install
```

---

## 10. Running the Application

Launch all three services in parallel:

```bash
./Start.sh
```

| Service | URL | Log |
|---|---|---|
| FastAPI backend | `http://localhost:8000` | `logs/backend.log` |
| Streamlit generator | `http://localhost:8501` | `logs/generator.log` |
| React dashboard | `http://localhost:5173` | `logs/frontend.log` |

**Generating and ingesting a dataset:**

1. Open `http://localhost:8501` (Streamlit generator)
2. Select row count (e.g. 10,000), target state, seed, and enable all anomaly scenarios
3. Click **Generate** and **Download CSV**
4. Open `http://localhost:5173/ingest`
5. Upload the downloaded CSV and click **Ingest**
6. Navigate to `/dashboard` — all metrics update from the live Neo4j data

---

## 11. Stopping the Application

```bash
./Kill.sh
```

To also wipe all Neo4j data:

```bash
docker compose down -v
```

---

## 12. Running Tests

```bash
cd chainwatch_backend
source venv/bin/activate
pytest tests/test_analytics.py tests/test_integration.py -v
```

Expected: **22/22 passed**

```
tests/test_analytics.py::test_peeling_chain_detection        PASSED
tests/test_analytics.py::test_coinjoin_mixing_detection      PASSED
tests/test_analytics.py::test_shap_explainer_output_structure PASSED
tests/test_analytics.py::test_shap_feature_names_match       PASSED
tests/test_analytics.py::test_risk_propagation               PASSED
... (9 analytics + 13 integration)
```

> `test_full_suite.py` contains 9 pre-existing failures against an older API shape. These are not regressions — `test_analytics.py` and `test_integration.py` are the authoritative test suites.

---

## 13. Dashboard Walkthrough

| Page | Path | What it shows |
|---|---|---|
| Landing | `/` | Platform overview, quick-start CTAs |
| Dashboard | `/dashboard` | KPI cards, India threat map, risk distribution, AI cluster chart, live ticker |
| Investigate | `/investigate/:address` | Force-directed graph, hop/direction controls, SHAP panel, timeline, inspector |
| Alerts | `/alerts` | Paginated table — filter by `detector`, `severity`, `min_risk` |
| Search | `/search` | Wallet address, txid, or IP lookup |
| Ingest | `/ingest` | CSV upload with ingest summary |
| About | `/about` | Methodology and platform documentation |

The investigation page accepts any wallet address, transaction ID, or IP from the alerts table directly in the URL: `http://localhost:5173/investigate/bc10b9a5bef23526e8d8a7e7e98b9091bc`

---

*ChainWatch — NTRO Proof of Concept. All processing is fully offline. No data leaves the local machine.*
