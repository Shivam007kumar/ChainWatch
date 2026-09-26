# ChainWatch Project Report

## 1. What this project is

ChainWatch is a local proof-of-concept for exploring Bitcoin transaction and network-observation data. A user uploads a CSV ledger. The system summarizes activity by wallet, estimates which wallets behave unusually, looks for a few recognizable transaction patterns, enriches observed IP addresses with offline location/network data, and presents the results as alerts, maps, graphs, and investigation pages.

The main question it helps an analyst explore is: **which observed wallets or transaction paths deserve a closer look, and what evidence in this dataset led to that lead?** It does not prove that a wallet owner committed a crime, and its scores should be treated as triage signals for human review.

The project has four main pieces:

1. **React web interface** — pages used to upload data, review alerts, search entities, and inspect a graph.
2. **FastAPI backend** — receives uploads, runs analysis, serves data to the interface, and creates PDF reports.
3. **Neo4j graph database** — stores wallets, transactions, IPs, datasets, alerts, and their relationships.
4. **Streamlit sample-data generator** — creates a synthetic CSV with example patterns for demonstrations.

## 2. Why it exists

Bitcoin addresses do not directly reveal a person's identity. A transaction ledger can show funds moving between addresses, while network observations may record IP addresses and capture times associated with transaction broadcasts. ChainWatch combines those two kinds of observations in one graph so an analyst can follow funds and inspect the network metadata available in the supplied data.

The project combines two kinds of analysis:

- **Pattern rules** find structures such as repeated split-and-change flows or transactions with many similarly sized outputs.
- **Unsupervised machine learning** looks for wallets whose measured behavior differs from other wallets in the same uploaded dataset.

This is a proof-of-concept using supplied or generated ledgers. It is not a live Bitcoin-network monitor, a wallet deanonymization service, or an independently validated law-enforcement system.

## 3. What data it accepts

The upload endpoint accepts a CSV file (up to 50 MB). The active parser in `chainwatch_backend/services/graph_builder.py` expects columns equivalent to:

| Field | Meaning |
| --- | --- |
| `txid` | Transaction identifier |
| `timestamp` | When the transaction was observed; if absent, the current time is substituted |
| `src_ip` | Source IP associated with the observation |
| `dst_ip` | Optional destination IP; defaults to `Unknown` |
| `src_port`, `dst_port` | Network ports; default to 0 and 8333 |
| `input_addresses` | JSON-like list of input wallet addresses |
| `input_amounts` | List of BTC amounts, in the same order as inputs |
| `output_addresses` | List of output wallet addresses |
| `output_amounts` | List of BTC amounts, in the same order as outputs |
| `fee` | Transaction fee; defaults to 0 |
| `script_type` | Script category; defaults to `P2PKH` |

List cells can be JSON arrays such as `["address1", "address2"]`; the legacy parser also attempts to accept Python-style single-quoted lists. The active path skips a row when one of these list fields cannot be parsed. It does not use the newer validator to check all fields, so callers should supply well-formed values, matching address/amount list lengths, valid timestamps, ports, and non-negative amounts.

The bundled generator creates 1,000 synthetic rows, can plant a six-step peeling sequence and a CoinJoin-like transaction, and lets the operator pick a target Indian state for some synthetic IP ranges. These records are illustrative, not real blockchain or subscriber attribution data.

## 4. Simple user flow

1. **Start the local services.** The user starts Neo4j separately with Docker Compose, then starts the backend, sample-data generator, and frontend using `Start.sh`.
2. **Prepare a ledger.** Either generate a demonstration CSV in the Streamlit app (port 8501) or provide a compatible CSV.
3. **Upload it.** On `/ingest` (or the older `/workspace` screen), choose the CSV and run the analysis. The upload is synchronous: the page waits for the backend to finish rather than polling a job-status API.
4. **Review the result.** The upload response reports a dataset ID, anomaly count, pattern counts, propagated-risk count, skipped rows, and whether the graph view was limited.
5. **Triage alerts.** On `/alerts`, filter and sort the saved alerts. Selecting an alert opens the wallet investigation route.
6. **Explore entities.** Search wallet addresses, transaction IDs, or IPs on `/search`; inspect a wallet graph, timeline, transaction, or IP information in the investigation views.
7. **Export a dossier.** The dashboard and older workspace provide links to a wallet PDF endpoint. The report is generated from the local anomaly JSON record (and uses a fallback template for an address that is not in that list).
8. **Reset when appropriate.** `/ingest` has a clear-workspace action. It deletes Neo4j graph data and resets the legacy JSON files; this operation is protected by an API key.

## 5. Frontend: what the user sees

The frontend is a React 19 single-page application built with Vite. `chainwatch_frontend/src/main.jsx` loads the app and global CSS; `App.jsx` maps browser paths to pages.

### Dashboard — `/`

`Home.jsx` is the older executive dashboard. It shows metric cards, charts, a map of India with wallet markers, a threat watchlist, and a switchable transaction/entity graph. Clicking a state filters the watchlist; selecting a wallet marker can open its graph, investigation page, or PDF dossier. The dashboard obtains its principal map/watchlist data from the legacy `/stats`, `/anomalies`, and `/graph` endpoints.

### Analyst workspace — `/workspace`

`Workspace.jsx` is the older three-column workflow: upload controls and reset on the left, map/graph and activity messages in the middle, and a suspect list on the right. The UI displays staged log messages while waiting for the synchronous upload request. Those intermediate messages are scheduled by the browser and are not live pipeline progress from the server. Prefer `/ingest` when demonstrating accurate request status.

### Ingest — `/ingest`

`pages/IngestPage.jsx` is the newer upload screen. It supports choosing or dropping a CSV, shows loading/success/error states, displays returned counts, links to the alerts page, and offers a confirmed clear-workspace action. The progress indicator reflects the request lifecycle, not individual backend stages.

### Alerts — `/alerts`

`pages/AlertsPage.jsx` requests server-filtered and paginated alerts. Filters include severity, detector, minimum risk, sort field, and order. Clicking an alert opens `/investigate/{entity_id}`.

### Investigation — `/investigate` and `/investigate/{address}`

`pages/InvestigationPage.jsx` is the graph investigation workspace. A wallet is selected from Alerts or Search; the page loads a bounded neighborhood and supports hop depth, flow direction, selecting a node or relationship, isolating a branch, hiding unrelated nodes, and opening an inspector. `InvestigationGraph.jsx` draws the semantic graph; `InspectorPanel.jsx` displays wallet, transaction, IP, or relationship details and cross-links between entities.

### Search — `/search`

`pages/SearchPage.jsx` searches wallet, transaction, and IP records. It requires at least four characters and can filter entity types. Wallet results go to a wallet investigation; transaction/IP query-string navigation is present in the UI, though the investigation page's current initial state is centered on a wallet address.

### About — `/about`

`pages/AboutPage.jsx` presents the project's purpose, methodology, capabilities, and architecture in a public-facing explainer.

### Shared visuals and API access

- `components/CwNav.jsx` is the navigation used by the newer pages and shows a backend status indicator.
- `components/MetricCards.jsx`, `ChartsView.jsx`, `AlertTable.jsx`, and `GraphView.jsx` render dashboard summaries and graph visuals.
- `mapUtils.js` positions wallet markers and derives map display data; `india.json` contains the map geometry.
- `api/client.js` centralizes API requests for the newer pages, adds the `X-API-Key` header to ingest/clear, and parses backend errors. The older `Home.jsx` and `Workspace.jsx` still use their own hard-coded API base and direct `fetch` calls.
- `index.css` supplies the shared interface styling. `index.html`, `public/`, and `src/assets/` hold the page shell and visual assets.

## 6. Backend and request flow

The backend is Python with FastAPI. `chainwatch_backend/main.py` creates the app, configures CORS, initializes database schema during startup, mounts the newer routers, and retains legacy file-backed routes. Startup attempts a Neo4j schema setup and connectivity check and logs GeoIP availability. Readiness can be checked at `/api/v1/health/ready`.

For an upload, the current active path is:

```text
Browser CSV upload
       ↓
POST /api/v1/ingest  (X-API-Key required)
       ↓
main.py checks extension, emptiness, and 50 MB limit
       ↓
services/graph_builder.py parses CSV rows and builds wallet/transaction summaries
       ↓
GeoIP/ASN enrichment + broadcast-time correlation
       ↓
14-feature wallet matrix → Isolation Forest + KMeans + SHAP explanations
       ↓
Peeling-chain + CoinJoin rules → graph risk propagation + co-spend links
       ↓
Neo4j batch writes (when available) and JSON view files
       ↓
Upload result returned to browser
```

Neo4j is attempted inside a guarded block: if graph persistence fails, the backend logs a warning and continues to write the legacy JSON output files. That supports the older dashboard paths, but the newer alerts, search, investigation, and database statistics depend primarily on Neo4j and may return empty/fallback responses if it is unavailable.

### Main API groups

| Route | Purpose |
| --- | --- |
| `GET /api/v1/health` | Fast process liveness response |
| `GET /api/v1/health/ready` | Checks Neo4j and GeoIP availability |
| `POST /api/v1/ingest` | Synchronous CSV upload and analysis; API key required |
| `GET /api/v1/stats` | Entity, risk, detector, and network totals; can scope by dataset ID |
| `GET /api/v1/alerts` | Filtered, sorted, paginated Neo4j alerts |
| `GET /api/v1/alerts/{alert_id}` | One persisted alert |
| `GET /api/v1/search` | Search wallet, transaction, and IP identifiers |
| `GET /api/v1/investigations/wallet/{address}` | Wallet summary and evidence |
| `GET /api/v1/investigations/wallet/{address}/graph` | Wallet neighborhood graph |
| `GET /api/v1/investigations/wallet/{address}/timeline` | Chronological wallet activity |
| `GET /api/v1/investigations/transaction/{txid}` | Transaction inputs, outputs, and network observations |
| `GET /api/v1/investigations/ip/{ip}` | IP enrichment and linked activity |
| `GET /api/v1/investigations/path` | Shortest-path trace between wallets; other strategies are reserved |
| `GET /api/v1/report/{wallet_id}` | Generate and return a PDF dossier |
| `POST` or `DELETE /api/v1/clear` | Clear Neo4j and JSON workspace state; API key required |

Older endpoints such as `/api/v1/anomalies`, `/api/v1/graph`, `/api/v1/peeling-chains`, and `/api/v1/mixers` read compatibility JSON files. They are what the older dashboard uses for its legacy map/graph views.

**Current routing caveat:** `main.py` registers its legacy file-backed `GET /api/v1/stats` before it includes the newer stats router, which registers the same method and path. FastAPI/Starlette uses the first matching route, so the legacy flat JSON response currently wins; the newer Neo4j-aggregated stats handler is shadowed. The newer `/stats` documentation and the actual response shape are therefore not fully aligned.

## 7. Machine learning and forensic analysis in plain language

### IP location and network enrichment

`services/geoip.py` looks up public source and destination IPs against local MaxMind City and ASN databases when available. It can also use bundled IP range CSV files for fallback location/ASN lookups. It returns state/city, coordinates, autonomous-system number, and organization where data exists. Private, invalid, unknown, or unmatched addresses stay unknown. An IP location is an estimate from a database; it does not identify a person or guarantee the physical location of the operator.

### Broadcast timing correlation

`analytics/correlation.py` groups observations by transaction ID and compares each capture time with the earliest capture. Within the configured 30-second window, it computes `exp(-delta / tau)` with tau defaulting to 8 seconds. Earlier observations receive higher values; late observations outside the configured window are discarded. This is a timing-based candidate score, not proof that an IP originated a transaction.

### Wallet behavior features

`services/graph_builder.py` calculates 14 dataset-relative measurements for each wallet:

1. Transaction count
2. Total observed BTC volume
3. Number of distinct source IPs
4. Transaction velocity over the observed time span
5. Relative variation in amounts
6. Number of distinct ASNs/providers
7. Cross-state IP ratio
8. Average transaction output count
9. Average source port
10. Average destination port
11. Source/destination state mismatch ratio
12. Fraction of transactions using selected script types (`P2SH`, `P2WSH`, `P2MS`)
13. Fraction of observed transactions whose input/output/fee balance check is negative beyond a small tolerance
14. Average broadcast timing score

The feature rows are standardized using `StandardScaler` so measurements with different scales can be compared by the models.

### Isolation Forest: unusual behavior detection

The active implementation fits scikit-learn's Isolation Forest with 200 trees, contamination set to 0.10, and a fixed random seed. It flags roughly the most unusual 10% of wallets in that particular upload. Its internal anomaly score is not a calibrated probability. The app rescales flagged wallets into a 60–99 range for display, so a displayed score should not be read as a real-world probability of wrongdoing. A small or synthetic dataset can produce unstable or unhelpful comparisons.

### SHAP: why a wallet was unusual

`analytics/shap_explainer.py` asks SHAP's TreeExplainer to attribute the Isolation Forest output across the 14 inputs. The UI/report can show top feature contributions, observed values, population deviation, and a plain-language reason. SHAP describes how the model's output relates to its features; it does not establish a causal explanation or validate the underlying data.

### KMeans: activity group labels

`KMeans` assigns wallets to up to six groups (or fewer when there are fewer wallets). Labels are produced from the strongest feature deviations in a group's center, for example “High-volume / Multi-IP Cluster.” Clustering answers “which wallets look similar in this upload?”; it is separate from Isolation Forest's “which wallets look unusual?”

### Peeling-chain detector

`analytics/peeling_chain.py` looks for two-output transactions where one output is above 80% and the other below 20%, then links the larger change output to the next transaction's input wallet. Paths with at least three linked hops are reported as candidate peeling chains. The small output is treated as a possible peel/cashout and the large output as continuing change. These are fixed pattern rules and can produce false positives or miss variants.

### CoinJoin-like detector

The same module flags transactions with at least three distinct inputs and three distinct outputs when all output amounts are within 2% of their mean. This is a heuristic for a mixing-like shape, not a definitive classification of a CoinJoin protocol transaction.

### Risk propagation and co-spend links

`analytics/risk_propagation.py` treats wallets flagged by anomaly or pattern rules as seeds, then walks the wallet-to-wallet flow graph up to four hops. A downstream wallet receives the highest seed score multiplied by `0.70^distance`. Wallets that co-appear as inputs can also receive a score up to 85% of a risky co-spender's score (`CIOU` heuristic). These links are investigative leads; shared-input ownership assumptions are not universally valid.

## 8. Data model and system architecture

Neo4j stores the evidence as connected entities rather than only as flat rows:

```text
(:Dataset)-[:CONTAINS_WALLET]->(:Wallet)
(:Dataset)-[:CONTAINS_TX]->(:Transaction)
(:Dataset)-[:OBSERVED_IP]->(:IP)
(:Wallet)-[:SENT {amount}]->(:Transaction)
(:Transaction)-[:RECEIVED_BY {amount}]->(:Wallet)
(:IP)-[:BROADCAST {confidence}]->(:Transaction)
(:Transaction)-[:OBSERVED_DESTINATION]->(:IP)
(:Wallet)-[:SAME_ENTITY_AS {reason}]-(:Wallet)
(:Alert)-[:TARGETS]->(:Wallet)
```

Dataset nodes help queries scope records to an upload. Uniqueness constraints protect wallet addresses, transaction IDs, IP addresses, dataset IDs, and alert IDs. Indexes support common risk, state, timestamp, ASN, severity, and dataset queries. The query modules in `db/queries/` centralize the Cypher used by wallet, transaction, IP, path, search, and common dataset operations. Batch writes use Cypher `UNWIND` and `MERGE` patterns to reduce per-row database calls and avoid duplicate entities.

The backend also maintains `anomaly_results.json`, `stats.json`, and `graph.json` for compatibility with the original dashboard. The modular pipeline's documentation says it can emit the same compatibility files, but it is not currently the active upload path.

## 9. Key files and what each does

### Project root and deployment

| File | Role |
| --- | --- |
| `README.md` | Initial overview, setup notes, and historical architecture description |
| `backend.md` | Detailed backend/reference notes; some statements are aspirational or from earlier designs, so compare against code |
| `report.md` | Existing backend verification/audit notes, not the general project guide |
| `PROJECT_REPORT.md` | This implementation-oriented project guide |
| `docker-compose.yml` | Starts only the local Neo4j database, with persistent Docker volumes and browser/Bolt ports |
| `Start.sh` | Starts FastAPI, Streamlit, and Vite processes and writes logs/PIDs; it does not start Neo4j |
| `Kill.sh` | Stops processes launched by the start script and sweeps matching processes |

### Backend

| File/folder | Role |
| --- | --- |
| `chainwatch_backend/main.py` | FastAPI app, startup, CORS, API-key check, active upload/clear/PDF endpoints, legacy routes |
| `chainwatch_backend/config.py` | Environment settings, Neo4j settings, upload/graph limits, GeoIP paths |
| `chainwatch_backend/services/graph_builder.py` | **Active** ingestion, feature building, model/rule orchestration, persistence, and legacy JSON output |
| `chainwatch_backend/ingestion/pipeline.py` | New modular pipeline implementation; currently marked transition/non-active |
| `chainwatch_backend/ingestion/validator.py` | Strict row validation for canonical transaction objects; not called by the current upload route |
| `chainwatch_backend/ingestion/jobs.py` and `models/domain/job.py` | In-memory ingestion job and stage tracking abstractions; no active public polling endpoint |
| `chainwatch_backend/analytics/` | Separate correlation, anomaly, clustering, SHAP, peeling/CoinJoin, and risk modules |
| `chainwatch_backend/services/geoip.py` | Offline IP city/state/coordinate and ASN enrichment |
| `chainwatch_backend/services/evidence.py` | Turns modular detection results into aggregated alert objects; primarily used by the new pipeline path |
| `chainwatch_backend/services/investigation/` | Wallet, transaction, IP, and path investigation services |
| `chainwatch_backend/api/` | Health, alerts, investigation, search, and stats route modules |
| `chainwatch_backend/db/neo4j_driver.py` | Shared Neo4j driver and query execution wrapper |
| `chainwatch_backend/db/schema.py` | Startup uniqueness constraints and performance indexes |
| `chainwatch_backend/db/queries/` | Cypher query builders and batch persistence/read functions |
| `chainwatch_backend/generator_app.py` | Streamlit synthetic ledger generator |
| `chainwatch_backend/requirements.txt` | Pinned Python dependencies |

### Frontend

| File/folder | Role |
| --- | --- |
| `chainwatch_frontend/src/App.jsx` | Page routing |
| `chainwatch_frontend/src/Home.jsx` | Legacy dashboard |
| `chainwatch_frontend/src/Workspace.jsx` | Legacy analyst upload workspace |
| `chainwatch_frontend/src/pages/` | New ingest, alerts, search, investigations, and about screens |
| `chainwatch_frontend/src/components/` | Navigation, maps/graphs, alert table, metrics, charts, and entity inspector |
| `chainwatch_frontend/src/api/client.js` | Shared API client and API-key injection for newer screens |
| `chainwatch_frontend/src/mapUtils.js`, `src/india.json` | Map geometry and marker helpers |
| `chainwatch_frontend/src/index.css` | Global styling and component styles |
| `chainwatch_frontend/package.json` | Vite/React dependencies and development/build scripts |

## 10. Local setup and operation

1. Install Docker Desktop or Docker Engine with Compose, Python, and Node.js/npm.
2. Start Neo4j from the project root with `docker compose up -d`. The compose file exposes Neo4j Browser on port 7474 and Bolt on port 7687, and retains its data in named volumes.
3. Configure `chainwatch_backend/.env` with a Neo4j password and any desired settings. `config.py` defaults to `bolt://localhost:7687`, database `neo4j`, and a local API key value. Change credentials and the API key for any shared deployment; do not commit secret values.
4. Create the backend Python environment and install `chainwatch_backend/requirements.txt`.
5. Install frontend dependencies in `chainwatch_frontend` with npm.
6. Run `./Start.sh` from the project root. It launches FastAPI on port 8000, Streamlit on port 8501, and Vite on port 5173.
7. Open the frontend at `http://localhost:5173`. API docs are available from FastAPI's standard `/docs` route while the backend is running.
8. Stop the app processes with `./Kill.sh`; stop Neo4j separately with `docker compose down`.

`docker compose down` preserves Neo4j's named-volume data. Removing volumes (`docker compose down -v`) deletes that database data. The application's clear-workspace endpoint is also destructive: it clears graph data and local generated workspace JSON files.

## 11. Important implementation notes and limits

These details matter when explaining the project accurately:

- The actual upload route calls `services.graph_builder.process_ledger_csv`. `ingestion/pipeline.py`, the canonical validator, modular alert aggregation, and ingestion job stage model are a parallel refactor/transition path, not the current route.
- The active graph builder hashes the uploaded bytes to make a dataset ID, but clears the existing Neo4j graph before writing the next upload. Although dataset scoping exists in the schema and newer APIs, the active ingest therefore behaves primarily as a single-current-dataset workspace; it is not presently a reliable multi-dataset archive.
- In the active graph builder, peeling-chain and CoinJoin detections affect seed risk scores and appear in the legacy graph JSON, but the persisted `(:Alert)` nodes are currently created from the Isolation Forest anomaly list. As a result, the newer Alerts page's detector filters should not be assumed to show standalone persisted alerts for every rule detector.
- The graph visualization is deliberately capped at 1,200 transactions for display and graph persistence from an upload. The ML calculation is performed using all parsed transaction records. The response reports when graph data was truncated.
- The upload's “confidence”/risk presentation uses a rescaled Isolation Forest anomaly score, not a calibrated probability. Pattern and propagation scores are rule-defined heuristics.
- The PDF endpoint reads `anomaly_results.json`, not the persisted alert detail, and a missing wallet is rendered using a generic propagated-threat fallback. A generated PDF should not be treated as an independently verified evidentiary finding.
- The configured 50 MB check is performed after the request body has been read into memory. This is a practical small-file guard, not a streaming upload limit.
- The Neo4j readiness endpoint requires Neo4j and at least one city GeoIP source (MMDB or location CSV). Startup logs database issues but does not itself stop the server when Neo4j cannot be reached.
- The project includes test files and an existing `report.md` describing a prior verification run. This report does not rerun those tests and describes behavior from source inspection.
- “Offline” here means the data enrichment assets and database can run locally. The frontend needs no remote map tile service for its bundled India map, but an operator still has to install dependencies and provide a local database/runtime. Avoid describing the system as a certified or production-secure air-gapped deployment without a separate deployment review.

## 12. In short

ChainWatch is a local analyst-facing demonstration that takes a Bitcoin/network-observation CSV, enriches IPs from local data, applies dataset-relative anomaly scoring and explicit transaction-pattern heuristics, stores a connected evidence graph, and gives analysts several ways to inspect the resulting leads. Its value is in bringing these exploratory views and methods together. Its findings depend on the quality and representativeness of the uploaded data and need human interpretation.
