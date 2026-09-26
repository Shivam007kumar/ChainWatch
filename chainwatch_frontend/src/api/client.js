/**
 * api/client.js
 * ─────────────
 * Centralised HTTP client for the ChainWatch backend.
 *
 * All requests go through `request()` — scattered raw fetch() calls in
 * Home.jsx and Workspace.jsx are NOT migrated here; they continue to work
 * against their own hardcoded const API.  New pages use this module only.
 *
 * API key:
 *   Destructive endpoints (POST /ingest, POST/DELETE /clear) require the
 *   X-API-Key header.  The value is read from the VITE_API_KEY env variable
 *   and falls back to the development default 'chainwatch-local'.
 *
 * Frozen contract endpoints covered here:
 *   POST   /ingest                                    ← requires API key
 *   GET    /health
 *   GET    /health/ready
 *   GET    /stats
 *   GET    /search
 *   GET    /alerts
 *   GET    /alerts/{id}
 *   GET    /investigations/wallet/{address}
 *   GET    /investigations/wallet/{address}/graph
 *   GET    /investigations/wallet/{address}/timeline
 *   GET    /investigations/transaction/{txid}
 *   GET    /investigations/ip/{ip}
 *   GET    /investigations/path
 *   GET    /report/{wallet_id}
 *   POST   /clear                                     ← requires API key
 *   DELETE /clear                                     ← requires API key
 *
 * Legacy endpoints (kept for backward compat with Home.jsx / Workspace.jsx):
 *   GET    /anomalies
 *   GET    /graph
 *   GET    /peeling-chains
 *   GET    /mixers
 */

export const API_BASE =
  import.meta.env?.VITE_API_BASE ?? 'http://localhost:8000/api/v1';

const API_KEY =
  import.meta.env?.VITE_API_KEY ?? 'chainwatch-local';

/** Endpoints that require the X-API-Key header. */
const PROTECTED_PATHS = new Set(['/ingest', '/clear']);

/**
 * Core fetch wrapper.
 *
 * @param {string} path     - e.g. '/health' or '/alerts?limit=50'
 * @param {object} options  - fetch init options (method, body, etc.)
 * @returns {Promise<any>}  - parsed JSON response body
 * @throws  {ApiError}      - structured error with status + detail
 */
async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;

  const headers = { ...(options.headers ?? {}) };

  // Inject API key for protected endpoints
  const basePath = path.split('?')[0];
  if (PROTECTED_PATHS.has(basePath) || basePath === '/clear') {
    headers['X-API-Key'] = API_KEY;
  }

  // Don't set Content-Type for FormData — browser sets it with boundary
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] ?? 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const json = await res.json();
      detail = json.detail ?? json.message ?? detail;
    } catch (_) { /* ignore parse errors */ }
    throw new ApiError(res.status, detail, path);
  }

  // 204 No Content — return null
  if (res.status === 204) return null;

  return res.json();
}

export class ApiError extends Error {
  constructor(status, detail, path) {
    super(detail);
    this.name    = 'ApiError';
    this.status  = status;
    this.detail  = detail;
    this.path    = path;
  }
}

// ── Health ───────────────────────────────────────────────────────────────────

/** Liveness probe — fast, no I/O on backend. */
export function getLiveness() {
  return request('/health');
}

/**
 * Readiness probe — returns { status, neo4j, geoip }.
 * Returns 503 (ApiError) if backend is not ready.
 */
export function getReadiness() {
  return request('/health/ready');
}

// ── Stats ─────────────────────────────────────────────────────────────────────

/**
 * Enriched statistics from Neo4j.
 * @param {string} [datasetId] - scope to specific ingest run
 */
export function getStats(datasetId) {
  const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
  return request(`/stats${q}`);
}

// ── Search ────────────────────────────────────────────────────────────────────

/**
 * Global search across wallet addresses, transaction IDs, and IP addresses.
 * @param {string}   query   - min 4 characters
 * @param {string[]} [types] - ['wallet','transaction','ip'] (default: all)
 * @param {number}   [limit] - max results (default 20, max 100)
 */
export function search(query, types = ['wallet', 'transaction', 'ip'], limit = 20) {
  const params = new URLSearchParams({
    q:     query,
    types: types.join(','),
    limit: String(limit),
  });
  return request(`/search?${params}`);
}

// ── Alerts ────────────────────────────────────────────────────────────────────

/**
 * Paginated alert list — all filtering/sorting on the server.
 *
 * @param {object} opts
 * @param {string}  [opts.datasetId]
 * @param {string}  [opts.severity]   - 'low'|'medium'|'high'|'critical'
 * @param {number}  [opts.minRisk]    - 0–100
 * @param {string}  [opts.detector]   - 'isolation_forest'|'peeling_chain'|...
 * @param {string}  [opts.sort]       - 'risk_score'|'created_at'|'severity'
 * @param {string}  [opts.order]      - 'asc'|'desc'
 * @param {number}  [opts.limit]      - default 50, max 100
 * @param {number}  [opts.offset]     - default 0
 */
export function getAlerts({
  datasetId,
  severity,
  minRisk,
  detector,
  sort     = 'risk_score',
  order    = 'desc',
  limit    = 50,
  offset   = 0,
} = {}) {
  const params = new URLSearchParams({ sort, order, limit: String(limit), offset: String(offset) });
  if (datasetId) params.set('dataset_id', datasetId);
  if (severity)  params.set('severity',   severity);
  if (minRisk != null) params.set('min_risk', String(minRisk));
  if (detector)  params.set('detector',   detector);
  return request(`/alerts?${params}`);
}

/**
 * Single alert by stable id (ALT-{dataset}-{seq}).
 * @param {string} alertId
 */
export function getAlert(alertId) {
  return request(`/alerts/${encodeURIComponent(alertId)}`);
}

// ── Investigation: Wallet ─────────────────────────────────────────────────────

/**
 * Full wallet summary — entity, risk, statistics, SHAP, evidence, IPs.
 * @param {string}  address
 * @param {string}  [datasetId]
 */
export function getWalletSummary(address, datasetId) {
  const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
  return request(`/investigations/wallet/${encodeURIComponent(address)}${q}`);
}

/**
 * Semantic neighborhood graph for a wallet.
 * @param {string}  address
 * @param {number}  [hops=2]       - 1–5
 * @param {string}  [direction='both'] - 'forward'|'backward'|'both'
 * @param {string}  [datasetId]
 */
export function getWalletGraph(address, hops = 2, direction = 'both', datasetId) {
  const params = new URLSearchParams({ hops: String(hops), direction });
  if (datasetId) params.set('dataset_id', datasetId);
  return request(`/investigations/wallet/${encodeURIComponent(address)}/graph?${params}`);
}

/**
 * Chronological timeline for a wallet.
 * @param {string}  address
 * @param {string}  [datasetId]
 * @param {number}  [limit=100]
 */
export function getWalletTimeline(address, datasetId, limit = 100) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (datasetId) params.set('dataset_id', datasetId);
  return request(`/investigations/wallet/${encodeURIComponent(address)}/timeline?${params}`);
}

// ── Investigation: Transaction ────────────────────────────────────────────────

/**
 * Full transaction detail — inputs, outputs, broadcasts, destinations.
 * Fee ratio and volumes are computed server-side.
 * @param {string}  txid
 * @param {string}  [datasetId]
 */
export function getTransactionDetail(txid, datasetId) {
  const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
  return request(`/investigations/transaction/${encodeURIComponent(txid)}${q}`);
}

// ── Investigation: IP ─────────────────────────────────────────────────────────

/**
 * IP investigation — GeoIP with provenance, ASN, observation history.
 * @param {string}  ip
 * @param {string}  [datasetId]
 */
export function getIpDetail(ip, datasetId) {
  const q = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : '';
  return request(`/investigations/ip/${encodeURIComponent(ip)}${q}`);
}

// ── Investigation: Path ───────────────────────────────────────────────────────

/**
 * Trace path between two wallet addresses.
 * strategy='shortest' is the only implemented strategy; others return 501.
 *
 * @param {string}  source
 * @param {string}  target
 * @param {number}  [maxHops=5]
 * @param {string}  [direction='both']
 * @param {string}  [strategy='shortest']
 */
export function getPath(source, target, maxHops = 5, direction = 'both', strategy = 'shortest') {
  const params = new URLSearchParams({
    source,
    target,
    max_hops:  String(maxHops),
    direction,
    strategy,
  });
  return request(`/investigations/path?${params}`);
}

// ── Ingest ────────────────────────────────────────────────────────────────────

/**
 * Upload a CSV ledger and run the full forensic ML pipeline.
 * Synchronous — waits for the complete pipeline to finish.
 * No job-polling endpoint exists in the frozen contract; do not fake progress.
 *
 * @param {File}   file     - the CSV File object from an <input type="file">
 * @returns {Promise<object>} - { dataset_id, anomalies_found, peeling_chains_found, ... }
 */
export function ingestLedger(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/ingest', {
    method:  'POST',
    body:    formData,
    headers: {},   // Content-Type set by browser (multipart/form-data with boundary)
  });
}

// ── Clear ─────────────────────────────────────────────────────────────────────

/**
 * Wipe the Neo4j database and reset all workspace JSON state.
 * Returns { message, warnings }.
 */
export function clearWorkspace() {
  return request('/clear', { method: 'POST' });
}

// ── Report ────────────────────────────────────────────────────────────────────

/**
 * Returns the URL of the PDF dossier for a wallet — open in a new tab.
 * (Not a fetch call — it's a direct URL for window.open.)
 * @param {string} walletId
 */
export function getReportUrl(walletId) {
  return `${API_BASE}/report/${encodeURIComponent(walletId)}`;
}

// ── Legacy endpoints (for backward compat with Home.jsx / Workspace.jsx) ─────
// These are NOT frozen — they may change. New pages must NOT use these.

export function getLegacyAnomalies(params = {}) {
  const q = new URLSearchParams();
  if (params.minRisk  != null) q.set('min_risk', String(params.minRisk));
  if (params.state)   q.set('state',   params.state);
  if (params.cluster) q.set('cluster', params.cluster);
  if (params.limit)   q.set('limit',   String(params.limit));
  return request(`/anomalies${q.toString() ? '?' + q : ''}`);
}

export function getLegacyGraph() {
  return request('/graph');
}

export function getLegacyPeelingChains() {
  return request('/peeling-chains');
}

export function getLegacyMixers() {
  return request('/mixers');
}
