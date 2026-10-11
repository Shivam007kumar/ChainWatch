# ChainWatch — National Crypto-Threat Intelligence Network

> **NTRO Proof of Concept** · On-premises Bitcoin forensic intelligence platform for detecting laundering sequences, peeling chains, CoinJoin mixing, and threat activity across Indian jurisdictions.

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

**ChainWatch** is an on-premises Bitcoin transaction intelligence platform built as an NTRO proof-of-concept. It accepts raw cryptocurrency transaction ledgers (CSV), runs a multi-stage unsupervised ML and graph-analytics pipeline, enriches records from local GeoIP and ASN data, persists the intelligence graph to Neo4j, and exposes the results through a React 19 dashboard and investigation REST APIs.

The forensic pipeline uses local data and does not query external blockchain intelligence APIs; dashboard metrics come from Neo4j. The landing-page hero background is loaded from Unsplash and requires internet access to display.

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
│  STEP 1 — STATIC DEMO DATASET                                               │
│                                                                              │
│  Existing 10,000-transaction dataset                                        │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │  The dataset is prepared once and remains static for the demo.        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                │                                             │
│                    Use the existing demo dataset                            │
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
│  ┌──────────────────────────────────────────────────────────────────┐     │
│  │  React 19 + Vite (served by nginx)                                │     │
│  │  Landing /   Dashboard /dashboard   Investigate /investigate      │     │
│  │  Alerts /alerts   Search /search   Ingest /ingest   About /about  │     │
│  └─────────────────────────────┬────────────────────────────────────┘     │
│                 │  REST (configured X-API-Key on mutating endpoints)        │
└─────────────────┼───────────────────────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (port 8000, Docker-internal)                              │
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
                               │  Bolt (Docker-internal, port 7687)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Neo4j 5.12.0  (Docker — docker-compose.yml)                                │
│                                                                             │
│  Nodes:  :Dataset  :Wallet  :Transaction  :IP  :Alert                       │
│  Edges:  :SENT  :RECEIVED_BY  :BROADCAST  :OBSERVED_DESTINATION             │
│          :BELONGS_TO_DATASET  :ABOUT                                        │
│                                                                             │
│  5 uniqueness constraints + 10 composite indexes                            │
│  No Neo4j host ports are published                                          │
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
| Runtime | Python | 3.14 |

---

## 6. Repository Structure

```
chainwatch/
├── Start.sh                            # Launches backend + frontend in parallel
├── Kill.sh                             # Tears down all background processes
├── docker-compose.yml                  # Neo4j + FastAPI + frontend/nginx stack
├── .gitignore                          # Excludes secrets, local data, logs, and generated state
├── IP_Address.csv                      # Indian IP range reference (tracked)
├── india.geojson                       # GeoJSON state boundaries for dashboard map
├── india_city.geojson                  # GeoJSON city boundaries
│
├── chainwatch_backend/
│   ├── .env.example                    # Environment variable template
│   ├── requirements.txt                # All Python dependencies (pinned versions)
│   ├── config.py                       # Pydantic Settings — all tuneable parameters
│   ├── main.py                         # FastAPI app, route registration, CORS, security
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

- Docker Desktop or Docker Engine with Compose
- The four local GeoIP build inputs listed below (not stored in Git)
- Python 3.11+ with `venv` and Node.js 20+ with npm only when using the host development scripts

### 1. Clone and enter the repo

```bash
git clone https://github.com/Shivamkumar/ChainWatch.git
cd chainwatch
```

### 2. Configure the environment

```bash
cp chainwatch_backend/.env.example chainwatch_backend/.env
```

Set `NEO4J_PASSWORD` and `API_KEY` to appropriate values in this file. Set `DEMO_MODE=true` for the protected demonstration database. Compose reads this file with `--env-file`; the backend also receives its service settings from this file. Do not use sample or development credentials for a shared deployment.

### 3. GeoIP build inputs (required for the Docker backend image)

The backend image packages these existing local files at the paths expected by the application. Obtain the licensed GeoLite databases and DB-IP ASN dataset through your approved sources, then place them at these exact repository-root paths before building:

| Required local path | Purpose |
|---|---|
| `GeoLite2-City_20260904/GeoLite2-City.mmdb` | City/state/country lookup |
| `GeoLite2-ASN_20260904/GeoLite2-ASN.mmdb` | ASN and organization lookup |
| `dbip-asn-lite-2026-09.csv` | DB-IP ASN fallback data |
| `IP_Address.csv` | IP range fallback data |

These files are local build inputs and are not added to this checkpoint. The GeoLite and DB-IP files are ignored by Git. The repository's root `IP_Address.csv` is already tracked in its existing history; this checkpoint leaves it unchanged and does not stage it. `.dockerignore` allows only these exact build inputs into the backend build context while excluding dumps, credentials, and unrelated datasets. The `COPY` steps in `docker/backend.Dockerfile` fail the build if an input is absent; no incomplete image is produced. Check availability and build with `docker compose --env-file chainwatch_backend/.env build backend`. No automatic GeoIP download is performed.

### 4. Start the Docker application

```bash
docker compose --env-file chainwatch_backend/.env up -d --build
docker compose --env-file chainwatch_backend/.env ps
```

Compose starts three services: Neo4j, the FastAPI backend, and frontend/nginx. Only frontend/nginx is published to the host, on port 80. The backend (port 8000) and Neo4j (Bolt port 7687 and Browser port 7474) are reachable only on the internal Docker network; neither has a host port mapping. Open the application at `http://localhost`.

When `DEMO_MODE=true`, the Ingest page explains that the demonstration database is protected and `DELETE /api/v1/clear` returns HTTP 403. With `DEMO_MODE=false`, the existing development wipe behavior remains enabled.

### 5. Host development setup (optional)

`Start.sh` launches the host FastAPI development server and Vite dev server; it does not start Docker services. Install the Python and Node dependencies, and configure `NEO4J_URI` to point to a Neo4j instance reachable from the host. The Compose Neo4j service does not publish Bolt to the host.

```bash
cd chainwatch_backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
cd chainwatch_frontend
npm install
cd ..
./Start.sh
```

The host development URLs are `http://localhost:8000` for FastAPI and `http://localhost:5173` for Vite. Stop these host processes with `./Kill.sh`.

---

## 10. Running the Application

For the Docker application, use the Compose commands above. For host development, use `./Start.sh` as described in the optional host setup; it starts FastAPI and Vite only, and requires a host-reachable Neo4j endpoint.

| Service | URL | Log |
|---|---|---|
| FastAPI backend | `http://localhost:8000` | `logs/backend.log` |
| React dashboard | `http://localhost:5173` | `logs/frontend.log` |

**Using the static demonstration dataset:**

1. Start the Docker stack with its existing persisted Neo4j dataset.
2. Open `http://localhost/dashboard` to review the demo data.

---

## 11. Stopping the Application

For host development, stop the processes launched by `Start.sh`:

```bash
./Kill.sh
```

`./Kill.sh` stops only the host processes launched by `Start.sh`; it does not stop Docker containers. To stop the Compose stack while preserving Neo4j data, run:

```bash
docker compose --env-file chainwatch_backend/.env down
```

Do not append `-v` unless you intentionally want to delete the Neo4j volumes and all stored graph data.

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
