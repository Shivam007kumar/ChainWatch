# ChainWatch Backend Documentation

This folder contains the full backend pipeline for ChainWatch — an offline Bitcoin transaction analysis platform that correlates network-layer data (IPs, ports) with blockchain data (wallets, TXIDs) to detect anomalous activity using machine learning.

The pipeline runs in three numbered steps, then is served via a FastAPI server. Each step produces output files that feed into the next.

---

## Files Overview

### Scripts (run in order)

#### `1_generate_data.py`
Generates synthetic Bitcoin transaction data and saves it to CSV.

This is the data source for the entire pipeline. It creates a realistic dataset by sampling wallets and IPs from fixed pools so entities recur across transactions — mimicking how real Bitcoin addresses get reused. It also deliberately plants a number of "anomalous" wallets with suspicious behavior (multiple IPs, high-risk countries, high transaction frequency) so the ML model has real signal to detect.

**Key behavior:**
- Creates a pool of 45 wallets and 30 IPs
- Generates 200 transaction records
- ~15% of transactions are routed through 6 planted anomalous wallets
- High-risk countries (Russia, Nigeria, Unknown) are biased toward anomalous transactions

**Outputs:**
- `synthetic_bitcoin_traffic.csv` — the full transaction dataset
- `ground_truth.json` — the list of planted anomalous wallet addresses (used later to measure ML recall)

---

#### `2_ingest_graph.py`
Reads the CSV and loads all transactions into a Neo4j graph database.

This script connects to a local Neo4j instance (via Bolt protocol at `localhost:7687`) and builds a property graph where transactions, IP addresses, and wallet addresses are all nodes connected by typed relationships. It clears any existing data first, making it safe to re-run.

**Graph schema created:**
- `(:Transaction)` — one node per TXID
- `(:IP)` — one node per unique IP address, tagged with country
- `(:Wallet)` — one node per unique wallet address
- `(:IP)-[:BROADCASTED]->(:Transaction)` — source IP that broadcast the tx
- `(:Transaction)-[:SENT_TO_NODE]->(:IP)` — destination IP
- `(:Wallet)-[:INPUT_TO_TX {amount}]->(:Transaction)` — wallet that sent BTC
- `(:Transaction)-[:OUTPUT_TO_WALLET {amount}]->(:Wallet)` — wallet that received BTC

**Requires:** Neo4j running (e.g., via `docker-compose.yml` in the repo root). Credentials: `neo4j / hackathon2026`.

---

#### `3_run_ml.py`
The core ML pipeline. Reads the CSV, engineers features per wallet, runs anomaly detection, clusters wallets, and writes all results used by the API.

**Steps performed:**

1. **GeoIP resolution** — attempts to resolve `src_ip` to a real country using an offline MaxMind GeoLite2 database (`.mmdb` file). Falls back to the CSV's `geo_country` field if the database isn't present. The fallback rate is reported honestly in the console output and `stats.json`.

2. **Feature engineering** — aggregates per-wallet behavioral features across all transactions:
   - `tx_count` — total number of transactions
   - `total_received` / `total_sent` — BTC volume
   - `unique_ip_count` — number of distinct IPs linked to the wallet
   - `country_diversity` — number of distinct countries
   - `high_risk_country_hits` — transactions involving Russia, Nigeria, or Unknown
   - `total_volume_btc` — combined BTC flow

3. **Isolation Forest** — unsupervised anomaly detection (200 estimators, 15% contamination). Flags statistically outlying wallets. Confidence scores are min-max normalized within the flagged set for a real relative ranking.

4. **K-Means clustering** — groups all wallets into up to 6 behavioral clusters with human-readable names (e.g., "High-Volume Laundering Node", "Cross-Border Flow Cell").

5. **Explainable reasons** — generates a plain-English reason string for each flagged wallet based on which features drove the anomaly score.

6. **Graph data export** — builds a node/edge JSON structure for the frontend graph visualization, covering the first 60 transactions.

**Outputs:**
- `anomaly_results.json` — ranked list of flagged wallets with scores, cluster info, and reasons
- `graph_data.json` — nodes and edges for the frontend force-directed graph
- `stats.json` — high-level summary counts for the dashboard

---

#### `main.py`
The FastAPI server that exposes all ML results to the React frontend via a REST API.

Serves pre-computed JSON files for near-zero-latency responses and also includes a live Neo4j endpoint for real-time graph queries.

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/api/v1/stats` | Dashboard summary stats (from `stats.json`) |
| `GET` | `/api/v1/anomalies` | Ranked anomalous wallets (from `anomaly_results.json`). Supports `?limit=` and `?min_confidence=` query params |
| `GET` | `/api/v1/graph` | Pre-computed graph nodes + edges (from `graph_data.json`) |
| `GET` | `/api/v1/graph/live` | Live query against the Neo4j database |
| `GET` | `/api/v1/clusters` | K-Means cluster summary aggregated from anomaly results |

**Run with:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

---

### Data Files (generated, not committed manually)

#### `synthetic_bitcoin_traffic.csv`
Raw transaction dataset produced by `1_generate_data.py`. Each row is one Bitcoin transaction with fields: `timestamp`, `src_ip`, `dst_ip`, `src_port`, `dst_port`, `txid`, `input_addresses`, `output_addresses`, `input_amounts`, `output_amounts`, `geo_country`.

#### `ground_truth.json`
Contains the list of wallet addresses that were deliberately planted as anomalous by `1_generate_data.py`. Used to compute precision/recall for the ML model — i.e., how many of the known-bad wallets the Isolation Forest actually recovered.

#### `anomaly_results.json`
Output of `3_run_ml.py`. A JSON array of flagged wallet objects, sorted by confidence score descending. Each entry includes the wallet address, confidence score, cluster ID and name, plain-English reason, and behavioral metrics (tx count, volume, IP count, high-risk hits).

#### `graph_data.json`
Output of `3_run_ml.py`. Contains `nodes` and `links` arrays formatted for `react-force-graph-2d`. Nodes are typed as `wallet`, `ip`, or `transaction`. Flagged nodes carry `"flagged": true` and are rendered in red on the frontend.

#### `stats.json`
Output of `3_run_ml.py`. A small JSON object with five top-level counts used by the dashboard's metric cards: `total_transactions`, `total_wallets`, `anomalies_detected`, `high_risk_wallets`, `clusters_identified`.

---

## Running the Full Pipeline

```bash
# 1. Generate synthetic data
python 1_generate_data.py

# 2. Load into Neo4j (requires Docker running)
python 2_ingest_graph.py

# 3. Run ML and produce all result files
python 3_run_ml.py

# 4. Start the API server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Steps 2 and 4 require Neo4j to be running. Start it with `docker compose up -d` from the repo root.
