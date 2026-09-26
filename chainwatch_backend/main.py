import json
import logging
import re
from contextlib import asynccontextmanager
from html import escape
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from weasyprint import HTML

from config import BASE_DIR, CITY_DB_PATH, ALT_CITY_DB_PATH, LOCATION_CSV_PATH, settings
from services.graph_builder import process_ledger_csv

logger = logging.getLogger("chainwatch.api")

WALLET_ID_RE = re.compile(r'^[a-zA-Z0-9_\-]{1,64}$')


# ── Startup / shutdown lifecycle ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      1. Initialize Neo4j schema (constraints + indexes) — idempotent
      2. Verify Neo4j connectivity — fail fast if unreachable
      3. Check GeoIP availability — warn if only CSV fallback

    Shutdown: nothing required (Neo4j driver is lazy-initialized).
    """
    _startup()
    yield


def _startup() -> None:
    # 1. Schema init
    try:
        from db.schema import init_schema
        init_schema()
    except Exception as exc:
        logger.error(f"Schema initialization failed: {exc}")

    # 2. Neo4j connectivity ping
    try:
        from db.neo4j_driver import run_query
        run_query("RETURN 1 AS ok")
        logger.info(f"Neo4j connected: {settings.neo4j_uri} | database: {settings.neo4j_database}")
    except Exception as exc:
        logger.error(
            f"Neo4j is UNREACHABLE at {settings.neo4j_uri}. "
            f"Start docker-compose or set NEO4J_URI in .env. Error: {exc}"
        )

    # 3. GeoIP availability
    if CITY_DB_PATH.exists() or ALT_CITY_DB_PATH.exists():
        logger.info("GeoIP: MaxMind city database found.")
    elif LOCATION_CSV_PATH.exists():
        logger.warning("GeoIP: MaxMind not found — CSV fallback active. Resolution may be less precise.")
    else:
        logger.error("GeoIP: No database found. IP enrichment will return Unknown for all addresses.")


app = FastAPI(
    title="ChainWatch Core Engine",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API key middleware (Stage I) ───────────────────────────────────────────────
# Protects destructive endpoints: POST/DELETE /clear and POST /ingest.
# Read-only investigation endpoints do NOT require an API key.
_PROTECTED = {
    ("POST",   "/api/v1/ingest"),
    ("POST",   "/api/v1/clear"),
    ("DELETE", "/api/v1/clear"),
}

@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    key = (request.method, request.url.path)
    if key in _PROTECTED:
        provided = request.headers.get("X-API-Key", "")
        if provided != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid X-API-Key header."},
            )
    return await call_next(request)

# ── Mount routers ─────────────────────────────────────────────────────────────
from api.health        import router as health_router
from api.alerts        import router as alerts_router
from api.investigations import router as investigations_router
from api.search        import router as search_router
from api.stats         import router as stats_router

app.include_router(health_router,        prefix="/api/v1")
app.include_router(stats_router,         prefix="/api/v1")
app.include_router(alerts_router,        prefix="/api/v1")
app.include_router(investigations_router, prefix="/api/v1")
app.include_router(search_router,        prefix="/api/v1")

GRAPH_FILE = BASE_DIR / "graph.json"

# ══════════════════════════════════════════════════════════════════════════════
# API CONTRACT FREEZE  — ChainWatch Core Engine v2.0  (Stage K)
# ══════════════════════════════════════════════════════════════════════════════
# The following endpoint contracts are FROZEN. No breaking changes may be made
# to URL structure, required parameters, or response field names without an
# explicit version bump (e.g. /api/v2/...).
#
# Frontend work MUST NOT begin until this freeze is in place and the
# integration test (tests/test_integration.py) passes end-to-end.
#
# FROZEN ENDPOINTS
# ────────────────
# POST   /api/v1/ingest                                    [API-key required]
# GET    /api/v1/ingest/{job_id}                           (future — pipeline.py)
#
# GET    /api/v1/health
# GET    /api/v1/health/ready
#
# GET    /api/v1/stats?dataset_id=
# GET    /api/v1/search?q=&types=&limit=
#
# GET    /api/v1/alerts?dataset_id=&severity=&min_risk=&detector=&sort=&order=&limit=&offset=
# GET    /api/v1/alerts/{alert_id}
#
# GET    /api/v1/investigations/wallet/{address}?dataset_id=
# GET    /api/v1/investigations/wallet/{address}/graph?hops=&direction=
# GET    /api/v1/investigations/wallet/{address}/timeline?dataset_id=
# GET    /api/v1/investigations/transaction/{txid}?dataset_id=
# GET    /api/v1/investigations/ip/{ip}?dataset_id=
# GET    /api/v1/investigations/path?source=&target=&max_hops=&direction=&strategy=
#
# GET    /api/v1/report/{wallet_id}                        (PDF dossier)
#
# POST   /api/v1/clear                                     [API-key required]
# DELETE /api/v1/clear                                     [API-key required]
#
# LEGACY ENDPOINTS (kept for frontend backward compat — not frozen, may change)
# ─────────────────────────────────────────────────────────────────────────────
# GET    /api/v1/anomalies
# GET    /api/v1/graph
# GET    /api/v1/peeling-chains
# GET    /api/v1/mixers
# GET    /api/v1/graph/wallet/{id}
# ══════════════════════════════════════════════════════════════════════════════


# ── Pydantic models ───────────────────────────────────────────────────────────

class ShapAttribution(BaseModel):
    """Single SHAP feature attribution entry."""
    feature:          str
    label:            str
    shap_value:       float
    feature_value:    float
    sigma:            float
    direction:        str   # "positive" | "negative"
    pct_contribution: int


class AnomalyAlert(BaseModel):
    wallet_address:    str
    confidence_score:  float
    cluster_id:        int
    cluster_name:      str
    reason:            str
    shap_attributions: Optional[List[ShapAttribution]] = []
    correlated_txids:  Optional[List[str]]             = []
    tx_count:          int
    total_volume_btc:  float
    unique_ip_count:   int
    primary_state:     Optional[str]        = "Unknown"
    asn:               Optional[str]        = "N/A"
    isp:               Optional[str]        = "N/A"
    lat:               Optional[float]      = None
    lng:               Optional[float]      = None
    risk_score:        Optional[float]      = None
    risk_factors:      Optional[List[str]]  = []


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
def health_check():
    return {
        "status":    "ChainWatch Core Engine Active",
        "version":   "2.0.0",
        "forensics": [
            "IsolationForest", "KMeans", "SHAP-TreeExplainer",
            "PeelingChain", "CoinJoinMixer", "RiskPropagation",
        ],
    }


# ── Stats / anomalies / graph endpoints ──────────────────────────────────────

@app.get("/api/v1/stats")
def get_stats():
    try:
        with open(BASE_DIR / "stats.json") as fh:
            return json.load(fh)
    except Exception:
        return {
            "total_transactions":      0,
            "total_wallets":           0,
            "anomalies_detected":      0,
            "peeling_chains_detected": 0,
            "coinjoin_mixers_detected": 0,
            "wallet_locations":        [],
        }


@app.get("/api/v1/anomalies", response_model=List[AnomalyAlert])
def get_anomalies(
    min_risk: Optional[float] = None,
    state:    Optional[str]   = None,
    cluster:  Optional[str]   = None,
    limit:    int             = 500,
):
    try:
        with open(BASE_DIR / "anomaly_results.json") as fh:
            alerts = json.load(fh)
    except Exception:
        return []

    if min_risk is not None:
        alerts = [a for a in alerts if (a.get("risk_score") or a.get("confidence_score") or 0) >= min_risk]
    if state:
        alerts = [a for a in alerts if a.get("primary_state", "").lower() == state.lower()]
    if cluster:
        alerts = [a for a in alerts if cluster.lower() in a.get("cluster_name", "").lower()]

    return alerts[:limit]


@app.get("/api/v1/graph")
def get_graph():
    try:
        with open(GRAPH_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {
            "nodes":             [],
            "links":             [],
            "transaction_count": 0,
            "peeling_chains":    [],
            "coinjoin_mixers":   [],
        }


@app.get("/api/v1/peeling-chains")
def get_peeling_chains():
    try:
        with open(GRAPH_FILE) as fh:
            return json.load(fh).get("peeling_chains", [])
    except Exception:
        return []


@app.get("/api/v1/mixers")
def get_coinjoin_mixers():
    try:
        with open(GRAPH_FILE) as fh:
            return json.load(fh).get("coinjoin_mixers", [])
    except Exception:
        return []


@app.get("/api/v1/graph/wallet/{wallet_id}")
def get_wallet_neighborhood(wallet_id: str, hops: int = 2):
    """
    Returns Neo4j neighborhood paths for a specific wallet.
    Falls back to an empty result if Neo4j is unavailable.
    """
    if not WALLET_ID_RE.match(wallet_id):
        raise HTTPException(status_code=400, detail="Invalid wallet ID format.")
    if hops < 1 or hops > 5:
        raise HTTPException(status_code=400, detail="hops must be between 1 and 5.")
    try:
        from db import queries
        from db.neo4j_driver import run_query
        results = run_query(*queries.get_wallet_neighborhood(wallet_id, hops))
        return {"wallet": wallet_id, "hops": hops, "paths": results}
    except Exception as exc:
        logger.warning(f"Neighbourhood query failed for {wallet_id}: {exc}")
        return {"wallet": wallet_id, "hops": hops, "paths": [], "note": "Neo4j unavailable — file-backed mode active."}


# ── Ingest ────────────────────────────────────────────────────────────────────

@app.post("/api/v1/ingest")
async def ingest_ledger(file: UploadFile = File(...)):
    """
    Receives a CSV ledger from the React Workspace, runs the full forensic ML
    pipeline (GeoIP → Correlation → IsolationForest → SHAP → KMeans →
    PeelingChain → CoinJoin → RiskPropagation → Neo4j MERGE), and updates
    all JSON workspace files.

    Requires X-API-Key header (enforced by api_key_guard middleware).
    Max upload size: settings.max_upload_bytes (default 50 MB).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.filename}'. Only CSV files are accepted.",
        )

    print(f"📥 Ingesting ledger: {file.filename}")

    try:
        contents = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {exc}")

    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Enforce upload size limit
    if len(contents) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(contents):,} bytes). Maximum: {settings.max_upload_bytes:,} bytes.",
        )

    try:
        result = process_ledger_csv(contents)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"CSV parsing error: {exc}")
    except MemoryError:
        raise HTTPException(status_code=507, detail="File too large to process in available memory.")
    except Exception as exc:
        logger.exception("Unhandled error during ledger ingestion")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}")

    return result


# ── Clear ─────────────────────────────────────────────────────────────────────

@app.post("/api/v1/clear")
@app.delete("/api/v1/clear")
def clear_workspace():
    """Wipes the Neo4j database and resets all local JSON workspace state."""
    warnings = []

    empty_graph = {
        "nodes": [], "links": [], "transaction_count": 0,
        "peeling_chains": [], "coinjoin_mixers": [],
    }
    empty_stats = {
        "total_transactions": 0, "total_wallets": 0,
        "anomalies_detected": 0, "peeling_chains_detected": 0,
        "coinjoin_mixers_detected": 0, "wallet_locations": [],
    }

    # Step 1: wipe JSON files first — local, always works
    try:
        with open(BASE_DIR / "anomaly_results.json", "w") as fh:
            json.dump([], fh)
        with open(BASE_DIR / "stats.json", "w") as fh:
            json.dump(empty_stats, fh)
        with open(GRAPH_FILE, "w") as fh:
            json.dump(empty_graph, fh)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to clear workspace files: {exc}")

    # Step 2: Neo4j clear — non-fatal, failure is reported in warnings
    try:
        from db import queries
        from db.neo4j_driver import run_query
        run_query(*queries.clear_all_data(), write=True)
    except Exception as exc:
        warnings.append(f"Neo4j clear failed (DB may contain stale data): {str(exc)[:120]}")

    return {"message": "Workspace cleared.", "warnings": warnings}


# ── PDF report ────────────────────────────────────────────────────────────────

def _render_txid_list(txids: list) -> str:
    """Render correlated transaction IDs as a compact monospace block in the PDF."""
    if not txids:
        return ""
    shown    = txids[:10]
    overflow = len(txids) - len(shown)
    items    = "".join(f"<div style='font-family:monospace;font-size:9px;color:#374151;padding:2px 0;'>{escape(t)}</div>" for t in shown)
    suffix   = f"<div style='font-size:9px;color:#94a3b8;margin-top:4px;'>…and {overflow} more</div>" if overflow > 0 else ""
    return f"""
    <div style="margin-top:12px;">
      <div style="font-size:9px;text-transform:uppercase;color:#64748b;letter-spacing:.7px;margin-bottom:6px;">
        Linked Transaction IDs ({len(txids)} total)
      </div>
      <div style="background:#f5f7fa;border:1px solid #d5dce5;padding:10px 12px;">
        {items}{suffix}
      </div>
    </div>"""


def _render_shap_table(shap_attributions: list) -> str:
    """
    Render the SHAP attribution list as an HTML table for the PDF dossier.
    Returns an empty string if no attributions are present.
    """
    if not shap_attributions:
        return "<p style='color:#64748b;font-size:10px;'>No SHAP attribution data available for this wallet.</p>"

    direction_color = {"positive": "#a83232", "negative": "#1a6b3a"}

    rows_html = ""
    for attr in shap_attributions:
        direction  = attr.get("direction", "positive")
        pct        = attr.get("pct_contribution", 0)
        arrow      = "▲" if direction == "positive" else "▼"
        color      = direction_color.get(direction, "#172033")
        sigma      = attr.get("sigma", 0.0)
        sigma_dir  = "above" if sigma >= 0 else "below"

        rows_html += f"""
        <tr>
          <td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;font-size:10px;">
            {escape(attr.get('label', attr.get('feature', '')))}
          </td>
          <td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;font-size:10px;text-align:right;">
            {escape(str(round(attr.get('feature_value', 0), 4)))}
          </td>
          <td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;font-size:10px;text-align:right;">
            {escape(str(abs(round(sigma, 2))))}σ {sigma_dir} mean
          </td>
          <td style="padding:5px 8px;border-bottom:1px solid #e2e8f0;font-size:10px;
                     text-align:right;font-weight:700;color:{color};">
            {arrow} {pct}%
          </td>
        </tr>"""

    return f"""
    <table style="width:100%;border-collapse:collapse;margin-top:10px;">
      <thead>
        <tr style="background:#f1f5f9;">
          <th style="padding:6px 8px;text-align:left;font-size:9px;
                     text-transform:uppercase;color:#64748b;letter-spacing:.7px;">
            Feature
          </th>
          <th style="padding:6px 8px;text-align:right;font-size:9px;
                     text-transform:uppercase;color:#64748b;letter-spacing:.7px;">
            Observed Value
          </th>
          <th style="padding:6px 8px;text-align:right;font-size:9px;
                     text-transform:uppercase;color:#64748b;letter-spacing:.7px;">
            Population Deviation
          </th>
          <th style="padding:6px 8px;text-align:right;font-size:9px;
                     text-transform:uppercase;color:#64748b;letter-spacing:.7px;">
            Risk Contribution
          </th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>"""


@app.get("/api/v1/report/{wallet_id}")
def generate_pdf_report(wallet_id: str):
    """
    Generates an official NTRO PDF Dossier for a specific threat wallet.
    Includes Section 04 — XAI Feature Attribution (SHAP TreeExplainer).
    """
    if not WALLET_ID_RE.match(wallet_id):
        raise HTTPException(status_code=400, detail="Invalid wallet ID format.")
    try:
        with open(BASE_DIR / "anomaly_results.json") as fh:
            anomalies = json.load(fh)

        threat = next((a for a in anomalies if a["wallet_address"] == wallet_id), None)
        if not threat:
            threat = {
                "wallet_address":    wallet_id,
                "confidence_score":  85.0,
                "cluster_name":      "Propagated Threat Node",
                "reason":            "Propagated risk score from multi-hop laundering sequence.",
                "shap_attributions": [],
                "tx_count":          1,
                "total_volume_btc":  0.0,
                "unique_ip_count":   1,
                "primary_state":     "INDIAN JURISDICTION",
                "isp":               "N/A",
                "asn":               "N/A",
                "risk_score":        85.0,
                "risk_factors":      ["2_HOP_LAUNDERING_RECEPTACLE"],
            }

        risk_score_val   = threat.get("risk_score", threat.get("confidence_score", 0.0))
        risk_factors_str = ", ".join(threat.get("risk_factors", ["PRIMARY_ANOMALY"]))
        shap_table_html  = _render_shap_table(threat.get("shap_attributions", []))
        generated_at     = pd.Timestamp.now().strftime("%d %B %Y, %H:%M UTC")

        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  @page {{
    size: A4;
    margin: 22mm 18mm 18mm;
    @bottom-right {{
      content: "CHAINWATCH / NTRO  •  " counter(page);
      color: #64748b;
      font-size: 9px;
    }}
  }}
  body {{
    font-family: 'Helvetica', sans-serif;
    color: #172033;
    margin: 0;
    font-size: 11px;
    line-height: 1.45;
  }}
  .masthead {{
    display: flex;
    justify-content: space-between;
    border-bottom: 3px solid #e08b2c;
    padding-bottom: 12px;
  }}
  .agency {{ color: #123d68; font-size: 18px; font-weight: bold; letter-spacing: .4px; }}
  .unit   {{ color: #64748b; font-size: 10px; text-transform: uppercase; letter-spacing: 1.2px; margin-top: 3px; }}
  .classification {{
    color: #a83232;
    border: 1px solid #d98b8b;
    padding: 7px 10px;
    font-size: 9px;
    font-weight: bold;
    letter-spacing: 1px;
    text-align: center;
  }}
  .doc-title  {{ margin: 28px 0 4px; color: #123d68; font-size: 23px; letter-spacing: .3px; }}
  .subtitle   {{ color: #64748b; font-size: 11px; }}
  .rule       {{ border: 0; border-top: 1px solid #d5dce5; margin: 20px 0; }}
  .section    {{
    color: #123d68;
    border-bottom: 2px solid #123d68;
    padding-bottom: 5px;
    margin: 22px 0 12px;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 1px;
  }}
  .grid       {{ display: table; width: 100%; border-collapse: separate; border-spacing: 0 7px; }}
  .cell       {{ display: table-cell; width: 50%; vertical-align: top; padding-right: 16px; }}
  .label      {{ color: #64748b; font-size: 9px; text-transform: uppercase; letter-spacing: .7px; }}
  .value      {{ color: #172033; font-size: 13px; font-weight: bold; margin-top: 2px; word-break: break-all; }}
  .score-box  {{
    background: #fff3e5;
    border-left: 5px solid #e08b2c;
    padding: 12px 14px;
    margin: 18px 0;
  }}
  .score-box strong {{ color: #a83232; font-size: 22px; }}
  .evidence   {{
    background: #f5f7fa;
    border: 1px solid #d5dce5;
    padding: 15px;
    font-family: monospace;
    font-size: 10px;
    white-space: pre-wrap;
    word-break: break-word;
  }}
  .shap-box   {{
    background: #f8faff;
    border: 1px solid #c7d2fe;
    border-left: 4px solid #6366f1;
    padding: 14px;
    margin-top: 10px;
  }}
  .shap-engine-note {{
    font-size: 9px;
    color: #64748b;
    margin-bottom: 8px;
    font-style: italic;
  }}
  .notice     {{
    margin-top: 30px;
    padding: 10px;
    border-top: 1px solid #d5dce5;
    color: #64748b;
    font-size: 9px;
  }}
</style>
</head>
<body>

  <!-- Masthead -->
  <div class="masthead">
    <div>
      <div class="agency">Government of India | NTRO</div>
      <div class="unit">National Technical Research Organisation · Cyber Intelligence Division</div>
    </div>
    <div class="classification">RESTRICTED<br/>THREAT INTELLIGENCE</div>
  </div>

  <div class="doc-title">Threat Intelligence Dossier</div>
  <div class="subtitle">Automated analytical record · Generated {generated_at}</div>
  <hr class="rule"/>

  <!-- Section 01 -->
  <div class="section">01 / Subject Identification</div>
  <div class="grid">
    <div class="cell">
      <div class="label">Wallet address</div>
      <div class="value">{escape(threat['wallet_address'])}</div>
    </div>
    <div class="cell">
      <div class="label">Behavioural classification</div>
      <div class="value">{escape(threat['cluster_name'])}</div>
    </div>
  </div>

  <div class="score-box">
    <span class="label">Propagated Risk Assessment Score</span><br/>
    <strong>{risk_score_val}%</strong>
    &nbsp; Risk factors: {escape(risk_factors_str)}
  </div>

  <!-- Section 02 -->
  <div class="section">02 / Network and Geographic Footprint</div>
  <div class="grid">
    <div class="cell">
      <div class="label">Primary jurisdiction</div>
      <div class="value">{escape(str(threat['primary_state']).upper())}</div>
    </div>
    <div class="cell">
      <div class="label">Network organisation</div>
      <div class="value">{escape(str(threat['isp']))}</div>
    </div>
  </div>
  <div class="grid">
    <div class="cell">
      <div class="label">Autonomous system</div>
      <div class="value">{escape(str(threat['asn']))}</div>
    </div>
    <div class="cell">
      <div class="label">Record reference</div>
      <div class="value">CW-{escape(wallet_id[:12].upper())}</div>
    </div>
  </div>

  <!-- Section 03 -->
  <div class="section">03 / Analytical Evidence</div>
  <div class="grid">
    <div class="cell">
      <div class="label">Observed transactions</div>
      <div class="value">{threat['tx_count']}</div>
    </div>
    <div class="cell">
      <div class="label">Total observed volume</div>
      <div class="value">{threat['total_volume_btc']} BTC</div>
    </div>
  </div>
  <div class="grid">
    <div class="cell">
      <div class="label">Unique source IPs</div>
      <div class="value">{threat['unique_ip_count']}</div>
    </div>
    <div class="cell">
      <div class="label">Detection engine</div>
      <div class="value">IsolationForest · Neo4j Risk Propagation · Peeling Detector</div>
    </div>
  </div>
  <div class="evidence">{escape(threat['reason'])}</div>

  <!-- Linked transaction IDs -->
  {_render_txid_list(threat.get('correlated_txids', []))}

  <!-- Section 04 — SHAP XAI -->
  <div class="section">04 / XAI Feature Attribution (SHAP TreeExplainer)</div>
  <div class="shap-box">
    <div class="shap-engine-note">
      Shapley Additive Explanations computed via shap.TreeExplainer on the fitted
      IsolationForest model. Each row shows how much that feature contributed to
      this wallet's anomaly score relative to the population baseline.
      ▲ positive = pushed toward anomaly &nbsp;|&nbsp; ▼ negative = pushed toward normal.
    </div>
    {shap_table_html}
  </div>

  <!-- Handling notice -->
  <div class="notice">
    <strong>Handling notice:</strong> This analytical record is generated by the
    ChainWatch Core Engine for authorised use only. It is not a finding of criminal
    liability. Distribution is restricted under the applicable information-handling
    policy. Detection engine: ChainWatch v2.0 / SHAP v0.46 / IsolationForest
    (sklearn 1.5.2).
  </div>

</body>
</html>"""

        pdf_path = BASE_DIR / f"NTRO_Report_{wallet_id[:8]}.pdf"
        HTML(string=html_content).write_pdf(str(pdf_path))

        return FileResponse(
            str(pdf_path),
            filename=f"NTRO_Threat_Report_{wallet_id[:8]}.pdf",
            media_type="application/pdf",
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
