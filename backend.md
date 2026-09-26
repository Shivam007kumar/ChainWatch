# ChainWatch Core Engine — Defense & Forensics Reference Manual (backend.md)
*Official Technical & Architectural Reference Manual for NTRO Problem Statement 26146*  
**Confidential / Technical Reference for Evaluation & Defense Presentations**

---

## 1. Executive Summary & Problem Framing

### 1.1 The Problem Statement (PS ID: 26146)
**Title**: *AI-Powered Monitoring & Analysis of Bitcoin Transaction Traffic*  
**Organization**: National Technical Research Organisation (NTRO)  
**Objective**: Build a complete, **offline-capable** intelligence system that ingests bulk Bitcoin transaction and network-layer telemetry, correlates on-chain blockchain activity with off-chain peer-to-peer (P2P) network broadcasts, applies explainable AI/ML models to detect anomalies and money-laundering typologies, and produces prioritized, mathematically substantiated forensic leads.

### 1.2 The Core Forensic Insight (The "Why")
Bitcoin is pseudonymous on-chain, but on-chain transactions do not appear out of thin air. Before a transaction is mined into a block, it must be **broadcast across the P2P gossip network** via TCP/IP. 
* By capturing early network broadcast timestamps, source IPs, destination peer connections, and ports, we bridge the gap between:
  1. **Blockchain Layer**: Pseudonymous Wallets, Transaction IDs (TXIDs), Script Types, UTXO splitting.
  2. **Network Layer**: Physical IPv4/IPv6 addresses, Autonomous System Numbers (ASNs), ISP infrastructure, Geographic state/city jurisdictions.
* **ChainWatch Core Engine** merges these two layers into a unified **Neo4j Property Graph**, executes unsupervised ML (**Isolation Forest**) with **TreeSHAP** local explainability, runs deterministic forensic heuristics (**Peeling Chains**, **CoinJoin Mixers**, **Common-Input-Ownership co-spending**), and exports court-admissible dossiers.

---

## 2. High-Level System Architecture

```
                          ┌──────────────────────────────────────────────┐
                          │         CSV / Raw Metadata Ingestion         │
                          │   (Timestamp, IPs, Ports, TXID, UTXOs, Fee)  │
                          └──────────────────────┬───────────────────────┘
                                                 │
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │   Stage B: Ingestion Validator & Normalizer  │
                          │        (CanonicalTransaction Dataclass)      │
                          └──────────────────────┬───────────────────────┘
                                                 │
                     ┌───────────────────────────┴───────────────────────────┐
                     ▼                                                       ▼
      ┌─────────────────────────────┐                         ┌─────────────────────────────┐
      │  P2P Broadcast Correlation  │                         │ Offline GeoIP & ASN Lookup  │
      │   exp(-Δt / τ) Decay Model  │                         │ (MaxMind mmdb / Fallbacks)  │
      └──────────────┬──────────────┘                         └──────────────┬──────────────┘
                     │                                                       │
                     └───────────────────────────┬───────────────────────────┘
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │  14-Dimensional Behavioral Feature Matrix    │
                          │   (Velocity, Fan-out, Script Risk, Routing)  │
                          └──────────────────────┬───────────────────────┘
                                                 │
                     ┌───────────────────────────┼───────────────────────────┐
                     ▼                           ▼                           ▼
      ┌─────────────────────────────┐ ┌─────────────────────┐ ┌─────────────────────────────┐
      │    Isolation Forest (ML)    │ │ KMeans Clustering   │ │   Forensic Rule Engines     │
      │  Contamination=0.10, N=200  │ │ Dynamic Centroid    │ │ • Peeling-Chain Subchains   │
      │  Decision Function Rescale  │ │ Z-Score Labeling    │ │ • CoinJoin Mixers (4x4)     │
      └──────────────┬──────────────┘ └──────────┬──────────┘ │ • CIOU Co-Spending Cluster  │
                     │                           │            │ • Risk Propagation (BFS)    │
                     ▼                           │            └──────────────┬──────────────┘
      ┌─────────────────────────────┐            │                           │
      │    TreeSHAP Explainability  │            │                           │
      │  Exact % Feature Attribution│            │                           │
      └──────────────┬──────────────┘            │                           │
                     │                           │                           │
                     └───────────────────────────┼───────────────────────────┘
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │   Evidence Aggregator (services/evidence.py) │
                          │        Generates Unified Alert Models        │
                          └──────────────────────┬───────────────────────┘
                                                 │
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │       Neo4j Enterprise Property Graph        │
                          │   (ACID Transactions, Uniqueness Constraints)│
                          │  Nodes: Wallet, Transaction, IP, Alert, DS   │
                          └──────────────────────┬───────────────────────┘
                                                 │
                                                 ▼
                          ┌──────────────────────────────────────────────┐
                          │    Frozen REST API (FastAPI - 17 Endpoints)  │
                          │    Investigation, Graphs, Search, Dossiers   │
                          └──────────────────────────────────────────────┘
```

---

## 3. Data Pipeline & Domain Modeling (Stage B)

Every piece of incoming data is coerced into an immutable, strictly validated domain entity before touching Neo4j or ML models.

### 3.1 `CanonicalTransaction` (`models/domain/transaction.py`)
Eliminates scattered dictionary indexing (`row["txid"]`) and enforces clean schema boundaries:
* **Identity**: `txid`, `timestamp`, `dataset_id`.
* **Blockchain Fields**: `input_addresses`, `output_addresses`, `input_amounts`, `output_amounts`, `fee`, `script_type` (`P2PKH`, `P2SH`, `P2WPKH`, etc.).
* **Network Fields**: `src_ip`, `dst_ip`, `src_port`, `dst_port`.
* **Enriched / Derived**: `src_geo`, `dst_geo`, `broadcast_confidence`, `balance_delta`.
* **Derived Properties**:
  * `input_volume_btc = sum(input_amounts)`
  * `output_volume_btc = sum(output_amounts)`
  * `fee_ratio = fee / input_volume_btc`
  * `has_balance_violation = balance_delta < -0.0001` (Flags illicit/fabricated records where output exceeds input + fee).

### 3.2 Ingestion Validator (`ingestion/validator.py`)
* Never raises unhandled exceptions on dirty inputs; returns a clean tuple: `(valid_transactions, rejected_rows)`.
* Enforces strict array-length parity (`len(input_addresses) == len(input_amounts)`).
* Produces explicit audit records in `RejectedRow` with row indices and rejection reasons.

### 3.3 Dataset Isolation in Graph Writes
* Every ingestion batch computes an immutable SHA-256 fingerprint: `dataset_id = sha256(file_bytes)[:16]`.
* Re-uploading the exact same dataset is **idempotent**: creates no duplicate nodes.
* Uploading different datasets containing identical wallets preserves global entity identity (`(:Wallet {address: ...})`) while maintaining dataset-scoped links (`(:Dataset)-[:CONTAINS_WALLET]->(:Wallet)`).

---

## 4. Machine Learning & Mathematical Foundations (Stage C)

### 4.1 The 14-Dimensional Behavioral Feature Matrix
For each wallet $w$, we construct a normalized feature vector $\mathbf{x}_w \in \mathbb{R}^{14}$:
1. **`tx_count`**: Total transaction participation frequency.
2. **`total_volume_btc`**: Cumulative Bitcoin volume transacted.
3. **`unique_ip_count`**: Number of distinct source IP addresses observed broadcasting for this wallet.
4. **`tx_velocity`**: Frequency per unit time ($\Delta t$). Burst velocity indicates automated botnets or rapid laundering.
5. **`amount_variance`**: Variance of output values (high variance indicates layering).
6. **`unique_asn_count`**: Number of distinct Autonomous Systems used (indicates VPN/proxy/Tor hopping).
7. **`cross_state_ip_ratio`**: Ratio of observations spanning multiple administrative states.
8. **`avg_output_count`**: Fan-out ratio per transaction.
9. **`avg_src_port`**: High ephemeral ports vs standard listening ports.
10. **`avg_dst_port`**: Frequency of communication with non-standard P2P ports (standard Bitcoin P2P is `8333`).
11. **`dst_src_state_match`**: Cross-state physical routing discrepancy ratio.
12. **`script_type_risk_ratio`**: Proportion of transactions using complex scripts (`P2SH`, `P2WSH`, `P2MS`) frequently abused in mixing.
13. **`balance_violation_ratio`**: Frequency of mathematical anomalies in inputs/outputs.
14. **`avg_broadcast_confidence`**: Mean empirical broadcast confidence from network listener nodes.

### 4.2 Unsupervised Anomaly Detection: Isolation Forest
* **Algorithm**: Ensemble of 200 Isolation Trees ($N_{\text{estimators}} = 200$), contamination parameter $\alpha = 0.10$.
* **Mathematical Premise**: Anomalous behavioral vectors require fewer random splits in feature space to isolate in tree terminal leaves than normal transactions.
* **Risk Score Calibration**: The raw signed decision function value $s(\mathbf{x}) \in [-0.5, 0.5]$ is mapped to an operational forensic risk scale $[60, 99]$:
$$\text{RiskScore}(\mathbf{x}) = 60 + 39 \cdot \frac{s_{\max} - s(\mathbf{x})}{s_{\max} - s_{\min}}$$
*(A score $\ge 90$ represents Critical severity; $70–89$ High; $50–69$ Medium; $<50$ Low).*

### 4.3 Local Explainability: TreeSHAP (SHAP-TreeExplainer)
* Judges will ask: *"Why did the AI flag this wallet?"*
* We do not output black-box probabilities. We compute exact **Shapley Additive Explanations (SHAP)** values $\phi_i$ satisfying the efficiency property:
$$\sum_{i=1}^{14} \phi_i = f(\mathbf{x}) - \mathbb{E}[f(\mathbf{x})]$$
* For each flagged wallet, the backend returns:
  * Top-3 contributing features.
  * Direction of attribution (`positive` increases anomaly score; `negative` decreases).
  * Exact percentage contribution:
$$\text{pct\_contribution}_i = \frac{|\phi_i|}{\sum_j |\phi_j|} \times 100$$
  * Human-readable explanation string (e.g., *"Burst transaction velocity (+44%) and high cross-state IP ratio (+31%)"*).

### 4.4 Behavioral Entity Clustering: KMeans with Dynamic Centroid Labeling
* Runs KMeans clustering ($k=6$) over the standardized feature space.
* **Dynamic Centroid Z-Score Labeling**: Rather than arbitrary cluster indices (`Cluster 0`, `Cluster 1`), the engine computes centroid z-scores against the population mean:
$$z_{c, i} = \frac{\mu_{c, i} - \mu_{\text{pop}, i}}{\sigma_{\text{pop}, i}}$$
* Descriptors for features where $z > 0.5$ are dynamically compounded into operational labels:
  * Example: *"Burst-Velocity / Multi-IP Cluster"*
  * Example: *"High-Volume / Cross-Jurisdiction Cluster"*

---

## 5. Domain Forensic Heuristics

In addition to unsupervised ML, the backend implements battle-tested blockchain forensic heuristics:

### 5.1 Peeling Chain Engine (`analytics/peeling_chain.py`)
* **Typology**: Money launderers split a large illicit balance by making repeated rapid payments: at each hop, a small amount is peeled off to a destination (cash-out/merchant), while the bulk of funds is sent back to a new change address owned by the same entity.
* **Detection Logic**:
  1. Transaction has 1 input address and 2 output addresses.
  2. One output is significantly smaller ($<20\%$ of total) or standard round value (the peel).
  3. The larger output (the change) becomes the single input to another 1-in-2-out transaction within a tight temporal window ($\Delta t \le 300\text{s}$).
  4. Traces recursive sequences $\ge 3$ hops long and flags both the seed wallet and all intermediate change wallets.

### 5.2 CoinJoin Mixing Detector (`analytics/peeling_chain.py`)
* **Typology**: Privacy mixers (Wasabi, Whirlpool, JoinMarket) obfuscate the transaction graph by combining inputs from multiple independent users and outputting identical, uniform values.
* **Detection Logic**:
  * $N \ge 3$ inputs and $M \ge 3$ outputs.
  * Checks for identical output amounts: if $\ge 3$ outputs have the exact same satoshi value (e.g., $4 \times 4.999\text{ BTC}$), it identifies a CoinJoin mixing transaction.
  * Tags participating input addresses as co-mixing entities.

### 5.3 Common-Input-Ownership Heuristic (CIOU)
* When a Bitcoin transaction consumes multiple inputs ($A_1, A_2, A_3$), all input addresses must produce valid private key signatures to spend the UTXOs.
* Unless it is an explicit CoinJoin transaction, the CIOU heuristic establishes that $A_1, A_2, A_3$ are controlled by the **same physical entity**.
* Graph representation: Creates bidirectional `[:SAME_ENTITY_AS {heuristic: 'CIOU'}]` relationships in Neo4j.

### 5.4 Network Broadcast Correlation Engine (`analytics/correlation.py`)
* When an unconfirmed transaction propagates across the Bitcoin network, peer listener nodes log observation timestamps $t_{\text{obs}}$.
* The initial peer observation $t_0$ indicates the originating physical node.
* Confidence decay model:
$$\text{Confidence}(t) = \exp\left(-\frac{\Delta t}{\tau}\right)$$
  *(where $\Delta t = t_{\text{obs}} - t_0$ and decay constant $\tau = 8.0\text{ seconds}$)*.
* Distinguishes true transaction broadcasters (`confidence > 0.85`) from passive relay peers (`confidence < 0.20`).

---

## 6. Neo4j Graph Model & Cypher Schema (Stage D)

Neo4j was chosen over traditional relational or document databases because tracing transaction hops in SQL requires recursive CTEs that degrade exponentially at $\text{hops} \ge 3$. In Neo4j, path traversals execute in sub-millisecond pointer-chasing operations.

### 6.1 Node Labels & Properties
1. **`(:Wallet)`**:
   * `address` (Unique String), `risk_score` (Float), `flagged` (Boolean), `cluster_name` (String), `state` (String), `asn` (String).
2. **`(:Transaction)`**:
   * `txid` (Unique String), `timestamp` (String/Datetime), `fee` (Float), `script_type` (String).
3. **`(:IP)`**:
   * `address` (Unique String), `state` (String), `city` (String), `country` (String), `asn` (String), `isp` (String), `latitude` (Float), `longitude` (Float).
4. **`(:Dataset)`**:
   * `id` (Unique String), `filename` (String), `records` (Integer), `ingested_at` (Datetime), `status` (String).
5. **`(:Alert)`**:
   * `id` (Unique String: `ALT-{dataset_id[:8]}-{seq:06d}`), `dataset_id` (String), `entity_id` (String), `entity_type` (String), `detector` (String), `risk_score` (Float), `severity` (String), `evidence_json` (String), `shap_json` (String), `created_at` (String).

### 6.2 Relationship Types
* `(:Wallet)-[:SENT {amount: Float}]->(:Transaction)`
* `(:Transaction)-[:RECEIVED_BY {amount: Float}]->(:Wallet)`
* `(:IP)-[:BROADCAST {confidence: Float, port: Int}]->(:Transaction)`
* `(:Transaction)-[:OBSERVED_DESTINATION {port: Int, state: String}]->(:IP)`
* `(:Wallet)-[:SAME_ENTITY_AS {heuristic: String}]->(:Wallet)`
* `(:Dataset)-[:CONTAINS_WALLET]->(:Wallet)`
* `(:Dataset)-[:CONTAINS_TX]->(:Transaction)`
* `(:Dataset)-[:OBSERVED_IP]->(:IP)`
* `(:Alert)-[:TARGETS]->(:Wallet)`

### 6.3 Schema Constraints & Indexes (`db/schema.py`)
* **Uniqueness Constraints**:
  * `wallet_address_unique` on `(w:Wallet) ASSERT w.address IS UNIQUE`
  * `transaction_txid_unique` on `(t:Transaction) ASSERT t.txid IS UNIQUE`
  * `ip_address_unique` on `(ip:IP) ASSERT ip.address IS UNIQUE`
  * `dataset_id_unique` on `(d:Dataset) ASSERT d.id IS UNIQUE`
  * `alert_id_unique` on `(a:Alert) ASSERT a.id IS UNIQUE`
* **Performance Indexes**:
  * `wallet_risk_score_idx`, `wallet_flagged_idx`, `tx_timestamp_idx`, `ip_asn_idx`, `alert_dataset_idx`, `alert_severity_idx`.

---

## 7. Frozen API Contract (FastAPI v2.0)

All 17 endpoints are strictly versioned under `/api/v1` and frozen.

### 7.1 System & Health
* `GET /api/v1/health`: Lightweight liveness probe (`{"status": "ok", "version": "2.0.0"}`).
* `GET /api/v1/health/ready`: Readiness probe verifying active Neo4j connectivity (`RETURN 1`) and local GeoIP database availability. Returns `503 Service Unavailable` if database is down.

### 7.2 Ingestion & Management (Protected by `X-API-Key: chainwatch-local`)
* `POST /api/v1/ingest`: Multipart file upload accepting bulk CSV metadata. Enforces 50 MB hard limit. Runs full pipeline and populates Neo4j.
* `POST /api/v1/clear` & `DELETE /api/v1/clear`: Clears Neo4j database state.

### 7.3 Forensic Investigation Endpoints
* `GET /api/v1/investigations/wallet/{address}`:
  * Full wallet forensic dossier: risk breakdown, cluster tag, SHAP attributions, evidence items, and associated physical IP observations.
* `GET /api/v1/investigations/wallet/{address}/graph?hops=2&direction=both`:
  * Returns pure semantic neighborhood graph (`nodes` with `risk_level`, `edges` with `type`).
  * **Strict Semantic Contract**: No UI hex color codes or frontend layout attributes in the API payload.
* `GET /api/v1/investigations/wallet/{address}/timeline`: Chronological audit log of inputs, outputs, and network captures.
* `GET /api/v1/investigations/transaction/{txid}`: Detailed transaction breakdown with inputs, outputs, fees, and P2P peer broadcast list.
* `GET /api/v1/investigations/ip/{ip}`: IP provenance, MaxMind GeoIP city/state coordinates, ASN, ISP, and linked wallet activities.
* `GET /api/v1/investigations/path?source=...&target=...&strategy=shortest`:
  * Multi-hop money-flow path tracer using shortest-path Cypher traversals.

### 7.4 Alerts & Intelligence
* `GET /api/v1/alerts`: Paginated alert feed with server-side sorting (`risk_score`, `created_at`, `severity`) and filtering (`dataset_id`, `severity`, `detector`, `min_risk`).
* `GET /api/v1/alerts/{alert_id}`: Direct lookup of stable `(:Alert)` node with deserialized evidence and SHAP payloads.

### 7.5 Global Search & Stats
* `GET /api/v1/search?q=...&types=wallet,transaction,ip&limit=20`: Indexed universal entity search (requires minimum 4 characters).
* `GET /api/v1/stats?dataset_id=...`: Server-side aggregated entity counters, severity breakdown, detection distribution, and geographic coverage.

### 7.6 Court Dossier Generation
* `GET /api/v1/report/{wallet_id}`: Streams a rendered, court-admissible forensic PDF dossier generated via WeasyPrint.

---

## 8. Presentation & Defense Cheat Sheet (How to Win SIH)

### 8.1 The 3-Minute Live Demo Script
1. **0:00 - 0:30 (The Ingest & Problem)**:
   * *"Respected judges, criminal syndicates rely on Bitcoin’s pseudonymity to layer funds. We will demonstrate how ChainWatch unmasks an illicit syndicate in real-time."*
   * Upload a fresh dataset generated from `generator_app.py`.
2. **0:30 - 1:15 (The Alert & AI Explainability)**:
   * Show the `/alerts` feed. The top alert appears with `risk_score: 96 (Critical)`.
   * Open the wallet: Show the **TreeSHAP explanation card**.
   * *"Our AI does not just flag wallets; it explains why: 44% attribution from burst velocity, 32% from multi-IP dispersion, combined with a 4-hop peeling chain."*
3. **1:15 - 2:15 (The Graph & Physical De-anonymization)**:
   * Open the **Interactive Graph**. Show the funds moving from the Seed Wallet $\rightarrow$ Peeling Chain $\rightarrow$ CoinJoin Mixer.
   * Expand the transaction’s `BROADCAST` edge: Show the **Source IP**.
   * Open the IP details: Reveal the physical geographic location (e.g., Pune, Maharashtra, ASN AS55836).
   * *"We have successfully traced on-chain crypto layering to physical Indian jurisdiction."*
4. **2:15 - 3:00 (The Deliverable)**:
   * Click **"Download Dossier"**. Open the generated PDF report (`NTRO_Report_...pdf`).
   * *"In under 3 minutes, an intelligence analyst has a signed, court-ready forensic report with zero internet dependency."*

### 8.2 Answering Tough Questions from Evaluators

* **Q: "Is your system really offline? Does it make external calls to Blockchain.com, Etherscan, or Google Maps?"**  
  * **A**: *"No, sir. ChainWatch is completely air-gapped. The Neo4j graph, the MaxMind GeoIP City and ASN databases, the Scikit-Learn/SHAP models, and the WeasyPrint reporting engine run 100% locally on localhost. No outbound network packets are transmitted."*

* **Q: "Why Isolation Forest instead of a Supervised Deep Learning model like GCN or XGBoost?"**  
  * **A**: *"In real-world cyber intelligence, illicit Bitcoin transactions have massive label scarcity—criminals constantly invent new laundering topologies. Supervised models overfit to known patterns and fail on zero-day typologies. Isolation Forest is unsupervised; it models intrinsic behavioral normality and flags anomalies without requiring labeled historical crime data. Furthermore, Isolation Forest natively supports exact local TreeSHAP attribution."*

* **Q: "How does your confidence score differ from your risk score?"**  
  * **A**: *"They measure two fundamentally different things. Risk Score (0–100) measures **threat severity** derived from our 14-feature Isolation Forest and forensic heuristics. Confidence Score (0.0–1.0) measures **empirical network certainty** derived from P2P gossip propagation timing via an exponential decay model ($e^{-\Delta t / \tau}$) to confirm the physical broadcaster vs passive relay nodes."*

* **Q: "Can your system handle high transaction throughput?"**  
  * **A**: *"Yes. The ingestion validator validates rows in stream memory, Cypher writes are batched using `UNWIND` parameter transactions, and all critical lookup keys (`address`, `txid`, `ip`, `alert_id`) are backed by Neo4j native B-tree uniqueness constraints and performance indexes."*

---

*ChainWatch Core Engine — Built for Defense, Forensics, and Tactical Clarity.*
