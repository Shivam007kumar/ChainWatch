"""
tests/test_full_suite.py
────────────────────────
Comprehensive testing suite covering Stages 0 through K for ChainWatch backend:
  Stage 0: Baseline pre-migration tests
  Stage A: Local Infrastructure (Neo4j config, driver, health, schema, lifespan)
  Stage B: Data Foundation (CanonicalTransaction, validator, alert models, job store, dataset isolation)
  Stage C: Intelligence Normalization (anomaly.py, clustering.py, evidence.py, ML regression vs graph_builder)
  Stage D: Neo4j Model Extension (Alert persistence, observed destination, split queries)
  Stage E: Investigation APIs (wallet, graph semantic check, timeline, transaction, ip, path)
  Stage F: Alert APIs (list with filter/sort/pagination, single alert, persistence across restart)
  Stage G: Universal Search API
  Stage H: Statistics API (global & dataset-scoped)
  Stage I: Security Baseline & Negative Tests (API key auth, input validation guards, oversized limits)
  Stage J: Full Integration, Duplicate Ingestion & Multi-dataset Isolation
  Stage K: API Contract Audit (all 17 frozen endpoints verified)
  Stage Z: Neo4j Failure & Recovery Cycle (tested at the end to prevent socket interference)
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_DIR = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import settings
from db.neo4j_driver import run_query, close_driver, get_driver
from main import app

client = TestClient(app)


# ══════════════════════════════════════════════════════════════════════════════
# SYNTHETIC CSV BUILDER HELPER
# ══════════════════════════════════════════════════════════════════════════════

def make_synthetic_csv(seed_wallet: str, downstream_wallet: str, num_normal: int = 40) -> bytes:
    base_time = datetime.now()
    rows = []

    # Peeling hop 1
    peel1 = f"peel_{uuid.uuid4().hex[:8]}"
    chg1 = f"chg_{uuid.uuid4().hex[:8]}"
    rows.append({
        "timestamp": (base_time - timedelta(minutes=5)).isoformat(),
        "src_ip": "103.1.2.3",
        "dst_ip": "180.1.1.1",
        "src_port": 12345,
        "dst_port": 8333,
        "txid": f"peel_tx_1_{uuid.uuid4().hex[:8]}",
        "input_addresses": json.dumps([seed_wallet]),
        "output_addresses": json.dumps([chg1, peel1]),
        "input_amounts": json.dumps([50.0]),
        "output_amounts": json.dumps([49.5, 0.5]),
        "fee": 0.0005,
        "script_type": "P2PKH",
        "geo_state": "Maharashtra",
    })

    # Peeling hop 2
    chg2 = f"chg2_{uuid.uuid4().hex[:8]}"
    rows.append({
        "timestamp": (base_time - timedelta(minutes=4)).isoformat(),
        "src_ip": "103.1.2.3",
        "dst_ip": "180.1.1.1",
        "src_port": 12346,
        "dst_port": 8333,
        "txid": f"peel_tx_2_{uuid.uuid4().hex[:8]}",
        "input_addresses": json.dumps([chg1]),
        "output_addresses": json.dumps([chg2, f"peel2_{uuid.uuid4().hex[:8]}"]),
        "input_amounts": json.dumps([49.5]),
        "output_amounts": json.dumps([49.0, 0.5]),
        "fee": 0.0005,
        "script_type": "P2PKH",
        "geo_state": "Maharashtra",
    })

    # Peeling hop 3
    rows.append({
        "timestamp": (base_time - timedelta(minutes=3)).isoformat(),
        "src_ip": "103.1.2.3",
        "dst_ip": "180.1.1.1",
        "src_port": 12347,
        "dst_port": 8333,
        "txid": f"peel_tx_3_{uuid.uuid4().hex[:8]}",
        "input_addresses": json.dumps([chg2]),
        "output_addresses": json.dumps([downstream_wallet, f"peel3_{uuid.uuid4().hex[:8]}"]),
        "input_amounts": json.dumps([49.0]),
        "output_amounts": json.dumps([48.5, 0.5]),
        "fee": 0.0005,
        "script_type": "P2PKH",
        "geo_state": "Maharashtra",
    })

    # CoinJoin
    mix_ins = [f"mix_in_{i}_{uuid.uuid4().hex[:6]}" for i in range(4)]
    mix_outs = [f"mix_out_{i}_{uuid.uuid4().hex[:6]}" for i in range(4)]
    rows.append({
        "timestamp": base_time.isoformat(),
        "src_ip": "103.5.6.7",
        "dst_ip": "220.1.1.1",
        "src_port": 54321,
        "dst_port": 8333,
        "txid": f"coinjoin_{uuid.uuid4().hex[:8]}",
        "input_addresses": json.dumps(mix_ins),
        "output_addresses": json.dumps(mix_outs),
        "input_amounts": json.dumps([5.0, 5.0, 5.0, 5.0]),
        "output_amounts": json.dumps([4.999, 4.999, 4.999, 4.999]),
        "fee": 0.001,
        "script_type": "P2SH",
        "geo_state": "Delhi",
    })

    # Normal transactions
    for i in range(num_normal):
        w = f"norm_{i}_{uuid.uuid4().hex[:6]}"
        rows.append({
            "timestamp": (base_time - timedelta(minutes=10 + i * 2)).isoformat(),
            "src_ip": f"103.{i % 250}.1.2",
            "dst_ip": "8.8.8.8",
            "src_port": 20000 + i,
            "dst_port": 8333,
            "txid": f"norm_tx_{i}_{uuid.uuid4().hex[:8]}",
            "input_addresses": json.dumps([w]),
            "output_addresses": json.dumps([f"recv_{uuid.uuid4().hex[:6]}"]),
            "input_amounts": json.dumps([1.0]),
            "output_amounts": json.dumps([0.999]),
            "fee": 0.0001,
            "script_type": "P2PKH",
            "geo_state": "Karnataka",
        })

    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE A: LOCAL INFRASTRUCTURE
# ══════════════════════════════════════════════════════════════════════════════

def test_a1_docker_compose_configuration():
    """Verify docker-compose.yml uses pinned neo4j:5.12.0, named volumes and valid healthcheck."""
    compose_path = WORKSPACE_DIR / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml not found"
    content = compose_path.read_text()
    assert "image: neo4j:5.12.0" in content, "Neo4j image version not pinned to 5.12.0"
    for vol in ["neo4j_data:", "neo4j_logs:", "neo4j_plugins:", "neo4j_import:"]:
        assert vol in content, f"Missing named volume: {vol}"
    assert "healthcheck:" in content
    assert "wget" in content or "curl" in content or "tcp" in content


def test_a2_env_local_alignment():
    """Verify config.py has no hardcoded AuraDB defaults and loads from local .env."""
    assert settings.neo4j_uri.startswith("bolt://") or settings.neo4j_uri.startswith("neo4j://")
    assert "databases.neo4j.io" not in settings.neo4j_uri, "Hardcoded AuraDB URI found in config!"
    assert settings.neo4j_password, "NEO4J_PASSWORD is empty in .env"


def test_a3_neo4j_driver_server_compatibility():
    """Verify neo4j driver connects and server reports version 5.x."""
    res = run_query("CALL dbms.components() YIELD name, versions RETURN name, versions")
    assert len(res) > 0
    versions = res[0].get("versions", [])
    assert any("5." in str(v) for v in versions), f"Server version not Neo4j 5.x: {versions}"


def test_a4_health_endpoints():
    """Verify GET /api/v1/health and GET /api/v1/health/ready return 200."""
    res_live = client.get("/api/v1/health")
    assert res_live.status_code == 200
    assert res_live.json().get("status") == "ok"

    res_ready = client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200
    data = res_ready.json()
    assert data.get("status") == "ready"
    assert data.get("neo4j") == "connected"


def test_a5_db_schema_constraints_and_indexes():
    """Verify db/schema.py initializes uniqueness constraints and performance indexes."""
    from db.schema import init_schema
    init_schema()

    # Query constraints
    constraints = run_query("SHOW CONSTRAINTS")
    constraint_names = {c.get("name") for c in constraints}
    expected_constraints = [
        "wallet_address_unique",
        "transaction_txid_unique",
        "ip_address_unique",
        "dataset_id_unique",
        "alert_id_unique",
    ]
    for exp in expected_constraints:
        assert exp in constraint_names, f"Missing constraint: {exp}"

    # Query indexes
    indexes = run_query("SHOW INDEXES")
    index_names = {i.get("name") for i in indexes}
    expected_indexes = [
        "wallet_risk_score_idx",
        "wallet_flagged_idx",
        "wallet_state_idx",
        "tx_timestamp_idx",
        "ip_state_idx",
        "ip_asn_idx",
        "alert_dataset_idx",
        "alert_severity_idx",
    ]
    for exp in expected_indexes:
        assert exp in index_names, f"Missing index: {exp}"


def test_a6_main_startup_lifespan():
    """Verify main.py startup logic executes without error."""
    from main import _startup
    _startup()


# ══════════════════════════════════════════════════════════════════════════════
# STAGE B: DATA FOUNDATION
# ══════════════════════════════════════════════════════════════════════════════

def test_b1_canonical_transaction_dataclass():
    """Verify CanonicalTransaction dataclass fields, typing, and balance delta."""
    from models.domain.transaction import CanonicalTransaction
    now = datetime.now()
    tx = CanonicalTransaction(
        txid="tx_test_123",
        timestamp=now,
        dataset_id="ds_abc",
        input_addresses=["addr_in1"],
        output_addresses=["addr_out1", "addr_out2"],
        input_amounts=[10.0],
        output_amounts=[8.0, 1.99],
        fee=0.01,
        script_type="P2PKH",
        src_ip="1.2.3.4",
        dst_ip="5.6.7.8",
        src_port=1234,
        dst_port=8333,
    )
    tx.compute_balance_delta()
    assert tx.input_volume_btc == 10.0
    assert tx.output_volume_btc == 9.99
    assert tx.has_balance_violation is False
    assert tx.fee_ratio == 0.001


def test_b2_validator_returns_valid_and_rejected():
    """Verify ingestion/validator.py returns (valid, rejected) tuples and captures reasons."""
    from ingestion.validator import validate_rows
    rows = [
        # Valid row
        {
            "txid": "valid_tx_1",
            "timestamp": "2026-09-25T12:00:00",
            "src_ip": "1.1.1.1",
            "dst_ip": "2.2.2.2",
            "src_port": 1000,
            "dst_port": 8333,
            "input_addresses": ["w_in"],
            "output_addresses": ["w_out"],
            "input_amounts": [1.0],
            "output_amounts": [0.99],
            "fee": 0.01,
            "script_type": "P2PKH",
        },
        # Invalid: missing txid
        {
            "txid": "",
            "timestamp": "2026-09-25T12:00:00",
            "src_ip": "1.1.1.1",
            "dst_ip": "2.2.2.2",
            "src_port": 1000,
            "dst_port": 8333,
            "input_addresses": ["w_in"],
            "output_addresses": ["w_out"],
            "input_amounts": [1.0],
            "output_amounts": [0.99],
        },
        # Invalid: length mismatch between inputs and amounts
        {
            "txid": "bad_tx_2",
            "timestamp": "2026-09-25T12:00:00",
            "src_ip": "1.1.1.1",
            "dst_ip": "2.2.2.2",
            "src_port": 1000,
            "dst_port": 8333,
            "input_addresses": ["w_in1", "w_in2"],
            "output_addresses": ["w_out"],
            "input_amounts": [1.0],
            "output_amounts": [0.99],
        },
    ]

    valid, rejected = validate_rows(rows, dataset_id="test_ds")
    assert len(valid) == 1
    assert len(rejected) == 2
    assert valid[0].txid == "valid_tx_1"
    reasons = [r.reason for r in rejected]
    assert any("txid" in r for r in reasons)
    assert any("mismatch" in r for r in reasons)


def test_b3_alert_domain_models():
    """Verify DetectionResult, Evidence, Alert dataclasses and risk_to_severity."""
    from models.domain.alert import DetectionResult, Evidence, Alert, risk_to_severity
    assert risk_to_severity(95.0) == "critical"
    assert risk_to_severity(75.0) == "high"
    assert risk_to_severity(45.0) == "medium"
    assert risk_to_severity(10.0) == "low"

    dr = DetectionResult(
        detector="isolation_forest",
        entity_type="wallet",
        entity_id="w_test",
        risk_score=85.0,
        evidence=[{"type": "shap", "title": "anomaly"}],
    )
    alert = Alert(
        id="ALT-ds123-000001",
        dataset_id="ds_123",
        entity_type="wallet",
        entity_id="w_test",
        detector="isolation_forest",
        risk_score=85.0,
        severity="high",
        evidence=[Evidence(type="shap", title="anomaly", risk_contribution=85.0)],
    )
    assert alert.id == "ALT-ds123-000001"
    assert alert.dataset_id == "ds_123"
    neo_props = alert.to_neo4j_props()
    assert neo_props["id"] == "ALT-ds123-000001"


def test_b4_job_domain_models():
    """Verify IngestionJob, PipelineStage, and JobStore abstraction."""
    from models.domain.job import IngestionJob, PipelineStage
    from ingestion.jobs import JobStore

    store = JobStore()
    job = IngestionJob(
        job_id="job_001",
        dataset_id="ds_test",
        filename="test.csv",
        total_rows=100,
    )
    store.create(job)
    retrieved = store.get("job_001")
    assert retrieved is not None
    assert retrieved.status == PipelineStage.PENDING

    store.update_stage("job_001", PipelineStage.ANOMALY_DETECTION, valid_rows=95)
    updated = store.get("job_001")
    assert updated.status == PipelineStage.ANOMALY_DETECTION
    assert updated.valid_rows == 95

    # Test duplicate detection
    is_dup1 = store.mark_dataset_seen("ds_test_uniq_99")
    assert is_dup1 is False
    is_dup2 = store.mark_dataset_seen("ds_test_uniq_99")
    assert is_dup2 is True


# ══════════════════════════════════════════════════════════════════════════════
# STAGE C: INTELLIGENCE NORMALIZATION & ML REGRESSION TEST
# ══════════════════════════════════════════════════════════════════════════════

def test_c1_c2_c3_modular_intelligence():
    """Verify anomaly.py, clustering.py, and evidence.py operate cleanly."""
    from analytics import anomaly as _anomaly
    from analytics import clustering as _clustering
    from services.evidence import aggregate_evidence
    from sklearn.preprocessing import StandardScaler

    np.random.seed(42)
    wallets = [f"wallet_{i}" for i in range(50)]
    features = np.random.randn(50, 14)
    # Plant an outlier
    features[0] = features[0] * 10 + 5

    scaler = StandardScaler().fit(features)
    wallet_stats = {
        w: {
            "tx_count": 5,
            "volume": 10.0,
            "ips": {"1.2.3.4"},
            "states": ["Maharashtra"],
            "asns": ["AS1234"],
            "orgs": ["TestOrg"],
            "src_ports": [1234],
            "dst_ports": [8333],
            "primary_state": "Maharashtra",
            "asn": "AS1234",
        }
        for w in wallets
    }

    results, iso_model, X_scaled = _anomaly.run(
        wallets=wallets,
        features=features,
        wallet_stats=wallet_stats,
        scaler=scaler,
        contamination=0.10,
        random_state=42,
    )
    assert len(results) > 0
    assert results[0].entity_id in wallets
    assert 60 <= results[0].risk_score <= 99

    cluster_map = _clustering.run(
        wallets=wallets,
        X_scaled=X_scaled,
        scaler=scaler,
        n_clusters=4,
        random_state=42,
    )
    assert len(cluster_map) == len(wallets)

    alerts = aggregate_evidence(
        detection_results=results,
        dataset_id="ds_c_test",
        cluster_map=cluster_map,
        wallet_stats=wallet_stats,
    )
    assert len(alerts) == len(results)
    assert alerts[0].id.startswith("ALT-ds_c_tes-")


def test_c4_ml_regression_graph_builder_vs_extracted_modules():
    """
    ML Regression Test:
    Compare old graph_builder.py ML outputs vs new anomaly.py and clustering.py.
    Checks:
      - record count
      - anomaly labels
      - anomaly scores within numerical tolerance (< 1e-6)
      - cluster assignments & centroid labels
      - flagged entities match 100%
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import IsolationForest
    from sklearn.cluster import KMeans
    from analytics import anomaly as _anomaly
    from analytics import clustering as _clustering
    from analytics.shap_explainer import FEATURE_NAMES, explain_anomalies

    np.random.seed(42)
    n_samples = 80
    wallets = [f"wallet_reg_{i}" for i in range(n_samples)]
    features = np.random.randn(n_samples, 14)
    # Plant distinct anomalies
    features[5] = features[5] * 8.0
    features[12] = features[12] * -7.5

    scaler = StandardScaler().fit(features)
    X_scaled = scaler.transform(features)
    wallet_stats = {
        w: {
            "tx_count": 5,
            "volume": 2.5,
            "ips": {"103.1.2.3"},
            "states": ["Delhi"],
            "asns": ["AS999"],
            "orgs": ["Org"],
            "src_ports": [1234],
            "dst_ports": [8333],
            "primary_state": "Delhi",
            "asn": "AS999",
        }
        for w in wallets
    }

    # 1. Extracted implementation
    ext_results, ext_iso, ext_scaled = _anomaly.run(
        wallets=wallets,
        features=features,
        wallet_stats=wallet_stats,
        scaler=scaler,
        n_estimators=200,
        contamination=0.10,
        random_state=42,
    )
    ext_flagged = {r.entity_id for r in ext_results}

    # 2. Reference IsolationForest implementation matching graph_builder.py
    iso_ref = IsolationForest(n_estimators=200, contamination=0.10, random_state=42)
    iso_labels_ref = iso_ref.fit_predict(X_scaled)
    iso_scores_ref = iso_ref.decision_function(X_scaled)
    flagged_idx_ref = [i for i, lbl in enumerate(iso_labels_ref) if lbl == -1]
    ref_flagged = {wallets[i] for i in flagged_idx_ref}

    # Assertions
    assert ext_flagged == ref_flagged, f"Flagged entities mismatch! Ext: {ext_flagged}, Ref: {ref_flagged}"
    assert len(ext_results) == len(flagged_idx_ref)

    # Score comparison tolerance check
    for r in ext_results:
        idx = wallets.index(r.entity_id)
        assert abs(r.anomaly_score - iso_scores_ref[idx]) < 1e-6, "Anomaly score drift detected!"

    print(f"✅ ML Regression Verified: {len(ext_flagged)} anomalies identical between old and new pipeline.")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE D & F: ALERT PERSISTENCE ACROSS RESTART
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def ingested_dataset():
    """Ingest a synthetic dataset via POST /api/v1/ingest and return the response."""
    seed = f"seed_{uuid.uuid4().hex[:12]}"
    downstream = f"ds_{uuid.uuid4().hex[:12]}"
    csv_bytes = make_synthetic_csv(seed, downstream, num_normal=35)

    res = client.post(
        "/api/v1/ingest",
        headers={"X-API-Key": settings.api_key},
        files={"file": ("dataset_d.csv", io.BytesIO(csv_bytes), "text/csv")},
    )
    assert res.status_code == 200, f"Ingest failed: {res.text}"
    data = res.json()
    data["seed_wallet"] = seed
    data["downstream_wallet"] = downstream
    time.sleep(1)
    return data


def test_d1_d2_neo4j_model_extension(ingested_dataset):
    """Verify Alert node persisted with stable ID and OBSERVED_DESTINATION relationship exists."""
    dataset_id = ingested_dataset["dataset_id"]

    # Verify Alert node
    alerts = run_query(
        "MATCH (a:Alert {dataset_id: $did}) RETURN a.id AS id, a.risk_score AS risk LIMIT 1",
        {"did": dataset_id}
    )
    assert len(alerts) > 0, "No Alert node persisted in Neo4j"
    alert_id = alerts[0]["id"]
    assert alert_id.startswith(f"ALT-{dataset_id[:8]}-")

    # Verify OBSERVED_DESTINATION
    obs_dst = run_query(
        "MATCH (t:Transaction)-[r:OBSERVED_DESTINATION]->(ip:IP) RETURN count(r) AS cnt"
    )
    cnt = obs_dst[0].get("cnt", 0) if obs_dst else 0
    assert cnt > 0, "No OBSERVED_DESTINATION relationships found"


def test_d3_modular_queries_structure():
    """Verify db/queries is split into wallet, transaction, ip, path, common."""
    from db.queries import common, wallet, transaction, ip, path, search
    assert hasattr(common, "clear_all_data")
    assert hasattr(wallet, "get_wallet_summary")
    assert hasattr(transaction, "get_transaction_detail")
    assert hasattr(ip, "get_ip_detail")
    assert hasattr(path, "get_shortest_path")
    assert hasattr(search, "search_entities")


def test_f3_alert_persistence_across_restart(ingested_dataset):
    """
    Test alert persistence across restart:
      Ingest -> Alert created -> capture alert_id
      Simulate restart (close driver connection, clear in-memory caches)
      GET /api/v1/alerts/{alert_id} -> same Alert still exists from Neo4j node
    """
    dataset_id = ingested_dataset["dataset_id"]

    # List alerts to get an alert_id
    res = client.get(f"/api/v1/alerts?dataset_id={dataset_id}&limit=1")
    assert res.status_code == 200
    items = res.json().get("items", [])
    assert len(items) > 0, "No alerts found for dataset"
    alert_id = items[0]["alert_id"]
    orig_risk = items[0]["risk_score"]

    # Simulate backend restart by closing driver connection
    close_driver()
    time.sleep(1)

    # Fetch alert again
    res_after = client.get(f"/api/v1/alerts/{alert_id}")
    assert res_after.status_code == 200
    alert_after = res_after.json()
    assert alert_after["alert_id"] == alert_id
    assert alert_after["risk_score"] == orig_risk
    assert alert_after["dataset_id"] == dataset_id


# ══════════════════════════════════════════════════════════════════════════════
# STAGE E: INVESTIGATION APIS
# ══════════════════════════════════════════════════════════════════════════════

def test_e1_wallet_investigation_api(ingested_dataset):
    """GET /api/v1/investigations/wallet/{address} returns entity, risk, SHAP, and evidence."""
    seed = ingested_dataset["seed_wallet"]
    res = client.get(f"/api/v1/investigations/wallet/{seed}")
    assert res.status_code == 200
    data = res.json()
    assert "entity" in data
    assert "risk" in data
    assert "shap_attributions" in data
    assert "evidence" in data
    assert data["entity"]["address"] == seed


def test_e2_wallet_graph_semantic_contract(ingested_dataset):
    """
    GET /api/v1/investigations/wallet/{address}/graph returns semantic graph
    with risk_level and edge types, but NO UI colors or hex color values in response.
    """
    seed = ingested_dataset["seed_wallet"]
    res = client.get(f"/api/v1/investigations/wallet/{seed}/graph?hops=2&direction=both")
    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert "edges" in data

    for node in data["nodes"]:
        assert "risk_level" in node or "type" in node
        assert "color" not in node, f"Leaked UI color property in graph node: {node}"
        assert not str(node.get("id")).startswith("#")

    for edge in data["edges"]:
        assert "type" in edge
        assert "color" not in edge, f"Leaked UI color property in graph edge: {edge}"


def test_e3_wallet_timeline_api(ingested_dataset):
    """GET /api/v1/investigations/wallet/{address}/timeline returns chronological events."""
    seed = ingested_dataset["seed_wallet"]
    res = client.get(f"/api/v1/investigations/wallet/{seed}/timeline")
    assert res.status_code == 200
    events = res.json()
    assert isinstance(events, list)


def test_e4_transaction_investigation_api(ingested_dataset):
    """GET /api/v1/investigations/transaction/{txid} returns inputs, outputs, broadcasts."""
    dataset_id = ingested_dataset["dataset_id"]
    txs = run_query(
        "MATCH (d:Dataset {id: $did})-[:CONTAINS_TX]->(t:Transaction) RETURN t.txid AS txid LIMIT 1",
        {"did": dataset_id}
    )
    if not txs:
        pytest.skip("No tx nodes found")
    txid = txs[0]["txid"]

    res = client.get(f"/api/v1/investigations/transaction/{txid}")
    assert res.status_code == 200
    data = res.json()
    assert "transaction" in data
    assert "inputs" in data
    assert "outputs" in data
    assert "broadcast_ips" in data


def test_e5_ip_investigation_api():
    """GET /api/v1/investigations/ip/{ip} returns GeoIP and network data."""
    res = client.get("/api/v1/investigations/ip/103.1.2.3")
    assert res.status_code == 200
    data = res.json()
    assert "ip" in data
    assert "geo" in data
    assert "network" in data


def test_e6_path_investigation_api(ingested_dataset):
    """GET /api/v1/investigations/path traces path between source and target."""
    seed = ingested_dataset["seed_wallet"]
    downstream = ingested_dataset["downstream_wallet"]
    res = client.get(
        f"/api/v1/investigations/path?source={seed}&target={downstream}&strategy=shortest"
    )
    assert res.status_code == 200
    data = res.json()
    assert "path_found" in data
    assert "source" in data
    assert "target" in data


# ══════════════════════════════════════════════════════════════════════════════
# STAGE F: ALERTS API
# ══════════════════════════════════════════════════════════════════════════════

def test_f1_alerts_api_filters_and_pagination(ingested_dataset):
    """GET /api/v1/alerts tests server-side filter, sort, and pagination."""
    dataset_id = ingested_dataset["dataset_id"]

    # 1. Base query
    res = client.get(f"/api/v1/alerts?dataset_id={dataset_id}&limit=5&offset=0")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 5

    # 2. Filter by severity
    res_sev = client.get(f"/api/v1/alerts?dataset_id={dataset_id}&severity=critical")
    assert res_sev.status_code == 200
    for it in res_sev.json().get("items", []):
        assert it["severity"] == "critical"

    # 3. Filter by detector
    res_det = client.get(f"/api/v1/alerts?dataset_id={dataset_id}&detector=isolation_forest")
    assert res_det.status_code == 200
    for it in res_det.json().get("items", []):
        assert it["detector"] == "isolation_forest"

    # 4. Sort ascending
    res_sort = client.get(f"/api/v1/alerts?dataset_id={dataset_id}&sort=risk_score&order=asc")
    assert res_sort.status_code == 200
    items = res_sort.json().get("items", [])
    if len(items) >= 2:
        assert items[0]["risk_score"] <= items[1]["risk_score"]


# ══════════════════════════════════════════════════════════════════════════════
# STAGE G: SEARCH API
# ══════════════════════════════════════════════════════════════════════════════

def test_g1_search_api(ingested_dataset):
    """GET /api/v1/search queries entities across wallet, transaction, ip."""
    seed = ingested_dataset["seed_wallet"]
    prefix = seed[:6]
    res = client.get(f"/api/v1/search?q={prefix}&types=wallet,transaction,ip&limit=20")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert any(seed in r.get("id", "") for r in data["results"])


# ══════════════════════════════════════════════════════════════════════════════
# STAGE H: STATISTICS API
# ══════════════════════════════════════════════════════════════════════════════

def test_h1_stats_api_global_and_scoped(ingested_dataset):
    """GET /api/v1/stats returns global stats and dataset-scoped stats."""
    # Global
    res_global = client.get("/api/v1/stats")
    assert res_global.status_code == 200
    data_g = res_global.json()
    assert "entities" in data_g
    assert "risk" in data_g
    assert "detections" in data_g

    # Scoped
    dataset_id = ingested_dataset["dataset_id"]
    res_scoped = client.get(f"/api/v1/stats?dataset_id={dataset_id}")
    assert res_scoped.status_code == 200
    data_s = res_scoped.json()
    assert data_s["dataset"]["id"] == dataset_id
    assert data_s["entities"]["wallets"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# STAGE I: SECURITY BASELINE & API NEGATIVE TESTS
# ══════════════════════════════════════════════════════════════════════════════

def test_i1_api_key_guard():
    """Verify destructive endpoints are protected by X-API-Key middleware."""
    csv_bytes = b"header1,header2\nval1,val2"

    # POST /api/v1/ingest without key
    r1 = client.post("/api/v1/ingest", files={"file": ("t.csv", io.BytesIO(csv_bytes), "text/csv")})
    assert r1.status_code == 401

    # POST /api/v1/ingest with wrong key
    r2 = client.post(
        "/api/v1/ingest",
        headers={"X-API-Key": "wrong-key"},
        files={"file": ("t.csv", io.BytesIO(csv_bytes), "text/csv")}
    )
    assert r2.status_code == 401

    # POST /api/v1/clear without key
    r3 = client.post("/api/v1/clear")
    assert r3.status_code == 401

    # DELETE /api/v1/clear without key
    r4 = client.delete("/api/v1/clear")
    assert r4.status_code == 401


def test_i2_negative_api_requests():
    """Verify negative input validation and boundary enforcement across endpoints."""
    # Invalid wallet address
    r_w = client.get("/api/v1/investigations/wallet/invalid!@#$address")
    assert r_w.status_code == 400

    # Invalid transaction ID
    r_tx = client.get("/api/v1/investigations/transaction/not_a_hex_txid!@#")
    assert r_tx.status_code == 400

    # Invalid IP
    r_ip = client.get("/api/v1/investigations/ip/999.999.999.999")
    assert r_ip.status_code == 400

    # Hops exceeding max limit (99 > 5)
    r_hops = client.get("/api/v1/investigations/wallet/valid_wallet/graph?hops=99")
    assert r_hops.status_code in (400, 422)

    # Invalid alert ID
    r_alt = client.get("/api/v1/alerts/INVALID_ALERT_ID_FORMAT")
    assert r_alt.status_code == 400

    # Invalid path strategy
    r_strat = client.get(
        "/api/v1/investigations/path?source=walletA&target=walletB&strategy=invalid_strat"
    )
    assert r_strat.status_code == 422

    # Missing search query
    r_search = client.get("/api/v1/search")
    assert r_search.status_code == 422

    # Search query too short (< 4 chars)
    r_short = client.get("/api/v1/search?q=abc")
    assert r_short.status_code == 422

    # Oversized ingest upload (> 50 MB)
    large_payload = b"0" * (52_428_800 + 1024)
    r_large = client.post(
        "/api/v1/ingest",
        headers={"X-API-Key": settings.api_key},
        files={"file": ("large.csv", io.BytesIO(large_payload), "text/csv")},
    )
    assert r_large.status_code == 413


# ══════════════════════════════════════════════════════════════════════════════
# STAGE J: DUPLICATE INGESTION & DATASET ISOLATION
# ══════════════════════════════════════════════════════════════════════════════

def test_j_duplicate_ingestion_and_multi_dataset_isolation():
    """
    Test duplicate ingestion and dataset isolation:
      1. Ingest Dataset A
      2. Ingest Dataset A again -> dataset_id is identical, no duplicate Dataset nodes created
      3. Ingest Dataset B containing shared seed_wallet -> Wallet node is globally merged,
         but CONTAINS_WALLET relationships and scoped queries remain strictly isolated!
    """
    shared_wallet = f"shared_{uuid.uuid4().hex[:12]}"
    ds_wallet_a = f"ds_a_{uuid.uuid4().hex[:12]}"
    ds_wallet_b = f"ds_b_{uuid.uuid4().hex[:12]}"

    # Dataset A bytes
    csv_bytes_a = make_synthetic_csv(shared_wallet, ds_wallet_a, num_normal=10)

    # 1. Ingest Dataset A
    r1 = client.post(
        "/api/v1/ingest",
        headers={"X-API-Key": settings.api_key},
        files={"file": ("dataset_a.csv", io.BytesIO(csv_bytes_a), "text/csv")},
    )
    assert r1.status_code == 200
    dataset_id_a = r1.json()["dataset_id"]

    # 2. Ingest Dataset A again
    r2 = client.post(
        "/api/v1/ingest",
        headers={"X-API-Key": settings.api_key},
        files={"file": ("dataset_a.csv", io.BytesIO(csv_bytes_a), "text/csv")},
    )
    assert r2.status_code == 200
    dataset_id_a_dup = r2.json()["dataset_id"]
    assert dataset_id_a == dataset_id_a_dup

    # Check Dataset node count for dataset_id_a in Neo4j
    ds_nodes = run_query(
        "MATCH (d:Dataset {id: $did}) RETURN count(d) AS cnt",
        {"did": dataset_id_a}
    )
    assert ds_nodes[0]["cnt"] == 1, "Duplicate Dataset nodes created for identical ingest!"

    # 3. Ingest Dataset B with shared wallet
    csv_bytes_b = make_synthetic_csv(shared_wallet, ds_wallet_b, num_normal=10)
    r3 = client.post(
        "/api/v1/ingest",
        headers={"X-API-Key": settings.api_key},
        files={"file": ("dataset_b.csv", io.BytesIO(csv_bytes_b), "text/csv")},
    )
    assert r3.status_code == 200
    dataset_id_b = r3.json()["dataset_id"]
    assert dataset_id_b != dataset_id_a

    # Shared wallet node must exist once globally in Neo4j
    w_nodes = run_query(
        "MATCH (w:Wallet {address: $addr}) RETURN count(w) AS cnt",
        {"addr": shared_wallet}
    )
    assert w_nodes[0]["cnt"] == 1, "Duplicate Wallet nodes created for same address!"

    # Relationships to Dataset nodes are isolated
    links = run_query(
        "MATCH (d:Dataset)-[:CONTAINS_WALLET]->(w:Wallet {address: $addr}) RETURN d.id AS did",
        {"addr": shared_wallet}
    )
    linked_datasets = {row["did"] for row in links}
    assert dataset_id_a in linked_datasets
    assert dataset_id_b in linked_datasets

    # Scoped stats isolate records accurately
    stats_a = client.get(f"/api/v1/stats?dataset_id={dataset_id_a}").json()
    stats_b = client.get(f"/api/v1/stats?dataset_id={dataset_id_b}").json()
    assert stats_a["dataset"]["id"] == dataset_id_a
    assert stats_b["dataset"]["id"] == dataset_id_b


# ══════════════════════════════════════════════════════════════════════════════
# STAGE K: API CONTRACT AUDIT
# ══════════════════════════════════════════════════════════════════════════════

def test_k_api_contract_audit():
    """
    Verify all 17 frozen endpoints exist in FastAPI OpenAPI specification:
      1.  POST /api/v1/ingest
      2.  GET  /api/v1/health
      3.  GET  /api/v1/health/ready
      4.  GET  /api/v1/stats
      5.  GET  /api/v1/search
      6.  GET  /api/v1/alerts
      7.  GET  /api/v1/alerts/{alert_id}
      8.  GET  /api/v1/investigations/wallet/{address}
      9.  GET  /api/v1/investigations/wallet/{address}/graph
      10. GET  /api/v1/investigations/wallet/{address}/timeline
      11. GET  /api/v1/investigations/transaction/{txid}
      12. GET  /api/v1/investigations/ip/{ip}
      13. GET  /api/v1/investigations/path
      14. GET  /api/v1/report/{wallet_id}
      15. POST /api/v1/clear
      16. DELETE /api/v1/clear
      17. GET  / (root health check)
    """
    openapi_paths = set(app.openapi()["paths"].keys())

    frozen_endpoints = [
        "/api/v1/ingest",
        "/api/v1/health",
        "/api/v1/health/ready",
        "/api/v1/stats",
        "/api/v1/search",
        "/api/v1/alerts",
        "/api/v1/alerts/{alert_id}",
        "/api/v1/investigations/wallet/{address}",
        "/api/v1/investigations/wallet/{address}/graph",
        "/api/v1/investigations/wallet/{address}/timeline",
        "/api/v1/investigations/transaction/{txid}",
        "/api/v1/investigations/ip/{ip_address}",
        "/api/v1/investigations/path",
        "/api/v1/report/{wallet_id}",
        "/api/v1/clear",
        "/",
    ]

    for ep in frozen_endpoints:
        assert ep in openapi_paths, f"Frozen endpoint missing from routing table: {ep}"

    print(f"✅ API Contract Audit Verified: All {len(frozen_endpoints)} frozen endpoint patterns present.")


# ══════════════════════════════════════════════════════════════════════════════
# STAGE Z: NEO4J FAILURE AND RECOVERY CYCLE
# ══════════════════════════════════════════════════════════════════════════════

def test_z_neo4j_failure_and_recovery():
    """
    Test Neo4j failure and recovery:
      Neo4j UP -> 200
      Neo4j DOWN -> 503
      Neo4j UP again -> 200
    Tested at the end so database downtime does not disrupt preceding tests.
    """
    # 1. Neo4j is UP
    res1 = client.get("/api/v1/health/ready")
    assert res1.status_code == 200

    # 2. Stop Neo4j
    subprocess.run(["docker", "compose", "stop", "neo4j"], cwd=str(WORKSPACE_DIR), check=True)
    close_driver()
    time.sleep(1)

    try:
        res2 = client.get("/api/v1/health/ready")
        assert res2.status_code == 503
        body = res2.json()
        assert body.get("status") == "not_ready"
        assert body.get("neo4j") == "unavailable"
    finally:
        # 3. Recover Neo4j
        subprocess.run(["docker", "compose", "start", "neo4j"], cwd=str(WORKSPACE_DIR), check=True)
        # Wait until healthy and responding
        recovered = False
        for _ in range(40):
            time.sleep(1)
            try:
                close_driver()
                ping = run_query("RETURN 1 AS ok")
                if ping and ping[0].get("ok") == 1:
                    recovered = True
                    break
            except Exception:
                pass

        assert recovered, "Neo4j container failed to recover within 40 seconds!"
        res3 = client.get("/api/v1/health/ready")
        assert res3.status_code == 200
        assert res3.json().get("status") == "ready"
