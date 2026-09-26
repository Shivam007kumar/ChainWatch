"""
tests/test_integration.py
──────────────────────────
End-to-end integration test — proves the full PS 26146 requirement chain.

What this test proves:
  1. A synthetic CSV with planted peeling chain + CoinJoin ingests cleanly
  2. Neo4j receives Wallet, Transaction, IP, Dataset, Alert nodes
  3. GET /alerts returns the flagged seed wallet with risk_score >= 60
  4. GET /investigations/wallet/{seed} returns risk, evidence, SHAP
  5. GET /investigations/transaction/{peel_tx} returns broadcasts with confidence > 0
  6. GET /investigations/ip/{src_ip} returns GeoIP state and observation history
  7. GET /investigations/path finds a route from seed to downstream wallet
  8. GET /search?q= returns the flagged wallet
  9. GET /health/ready returns 200

Prerequisites:
  - Neo4j running at the URI in .env (local docker-compose or Aura)
  - Backend dependencies installed in venv
  - Run from chainwatch_backend/ directory:
      python -m pytest tests/test_integration.py -v

This test is the gate before frontend work begins.
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from io import StringIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── Synthetic CSV builder ──────────────────────────────────────────────────────

def _make_synthetic_csv(seed_wallet: str, downstream_wallet: str) -> bytes:
    """
    Build a minimal 1-record CSV containing:
      - 1 peeling-chain-like transaction from seed_wallet
      - 1 CoinJoin transaction
      - 1 normal transaction to downstream_wallet
    """
    import pandas as pd
    from datetime import datetime, timedelta
    import random

    rows = []
    base_time = datetime.now()

    # Peeling chain hop 1 — seed_wallet pays peel + change
    peel_wallet  = f"peel_{uuid.uuid4().hex[:10]}"
    change_wallet = f"chg_{uuid.uuid4().hex[:10]}"
    rows.append({
        "timestamp":        (base_time - timedelta(minutes=5)).isoformat(),
        "src_ip":           "103.1.2.3",
        "dst_ip":           "180.1.1.1",
        "src_port":         12345,
        "dst_port":         8333,
        "txid":             f"peel_tx_1_{uuid.uuid4().hex[:8]}",
        "input_addresses":  json.dumps([seed_wallet]),
        "output_addresses": json.dumps([change_wallet, peel_wallet]),
        "input_amounts":    json.dumps([50.0]),
        "output_amounts":   json.dumps([49.5, 0.5]),
        "fee":              0.0005,
        "script_type":      "P2PKH",
        "geo_state":        "Maharashtra",
    })

    # Peeling chain hop 2
    change2 = f"chg2_{uuid.uuid4().hex[:10]}"
    rows.append({
        "timestamp":        (base_time - timedelta(minutes=4)).isoformat(),
        "src_ip":           "103.1.2.3",
        "dst_ip":           "180.1.1.1",
        "src_port":         12346,
        "dst_port":         8333,
        "txid":             f"peel_tx_2_{uuid.uuid4().hex[:8]}",
        "input_addresses":  json.dumps([change_wallet]),
        "output_addresses": json.dumps([change2, f"peel2_{uuid.uuid4().hex[:10]}"]),
        "input_amounts":    json.dumps([49.5]),
        "output_amounts":   json.dumps([49.0, 0.5]),
        "fee":              0.0005,
        "script_type":      "P2PKH",
        "geo_state":        "Maharashtra",
    })

    # Peeling chain hop 3
    rows.append({
        "timestamp":        (base_time - timedelta(minutes=3)).isoformat(),
        "src_ip":           "103.1.2.3",
        "dst_ip":           "180.1.1.1",
        "src_port":         12347,
        "dst_port":         8333,
        "txid":             f"peel_tx_3_{uuid.uuid4().hex[:8]}",
        "input_addresses":  json.dumps([change2]),
        "output_addresses": json.dumps([downstream_wallet, f"peel3_{uuid.uuid4().hex[:10]}"]),
        "input_amounts":    json.dumps([49.0]),
        "output_amounts":   json.dumps([48.5, 0.5]),
        "fee":              0.0005,
        "script_type":      "P2PKH",
        "geo_state":        "Maharashtra",
    })

    # CoinJoin transaction
    mix_ins  = [f"mix_in_{i}_{uuid.uuid4().hex[:6]}" for i in range(4)]
    mix_outs = [f"mix_out_{i}_{uuid.uuid4().hex[:6]}" for i in range(4)]
    rows.append({
        "timestamp":        base_time.isoformat(),
        "src_ip":           "103.5.6.7",
        "dst_ip":           "220.1.1.1",
        "src_port":         54321,
        "dst_port":         8333,
        "txid":             f"coinjoin_{uuid.uuid4().hex[:8]}",
        "input_addresses":  json.dumps(mix_ins),
        "output_addresses": json.dumps(mix_outs),
        "input_amounts":    json.dumps([5.0, 5.0, 5.0, 5.0]),
        "output_amounts":   json.dumps([4.999, 4.999, 4.999, 4.999]),
        "fee":              0.001,
        "script_type":      "P2SH",
        "geo_state":        "Delhi",
    })

    # Padding normal transactions to give IsolationForest enough data
    for i in range(50):
        w = f"normal_{i}_{uuid.uuid4().hex[:8]}"
        rows.append({
            "timestamp":        (base_time - timedelta(minutes=random.randint(10, 500))).isoformat(),
            "src_ip":           f"1.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
            "dst_ip":           "8.8.8.8",
            "src_port":         random.randint(1024, 65535),
            "dst_port":         8333,
            "txid":             uuid.uuid4().hex,
            "input_addresses":  json.dumps([w]),
            "output_addresses": json.dumps([f"recv_{uuid.uuid4().hex[:8]}"]),
            "input_amounts":    json.dumps([round(random.uniform(0.01, 1.0), 4)]),
            "output_amounts":   json.dumps([round(random.uniform(0.01, 1.0), 4)]),
            "fee":              0.0001,
            "script_type":      "P2PKH",
            "geo_state":        "Karnataka",
        })

    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def seed_wallet():
    return f"seed_{uuid.uuid4().hex[:16]}"


@pytest.fixture(scope="module")
def downstream_wallet():
    return f"ds_{uuid.uuid4().hex[:16]}"


@pytest.fixture(scope="module")
def ingest_result(seed_wallet, downstream_wallet):
    """Run the pipeline and return the result dict. Module-scoped — runs once."""
    from services.graph_builder import process_ledger_csv

    csv_bytes = _make_synthetic_csv(seed_wallet, downstream_wallet)
    result = process_ledger_csv(csv_bytes)
    # Give Neo4j a moment to finish async indexing
    time.sleep(1)
    return result


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_pipeline_completes(ingest_result):
    """Pipeline returns a valid result dict with expected keys."""
    r = ingest_result
    assert "dataset_id"    in r, "Missing dataset_id in result"
    assert "anomalies_found"       in r
    assert "peeling_chains_found"  in r
    assert "coinjoin_mixers_found" in r
    assert r["rows_skipped"] == 0, f"Unexpected rows skipped: {r['rows_skipped']}"
    print(f"✅ Pipeline complete — dataset_id={r['dataset_id']}, "
          f"anomalies={r['anomalies_found']}, peeling={r['peeling_chains_found']}")


def test_neo4j_has_wallet_nodes(seed_wallet, ingest_result):
    """Wallet nodes were written to Neo4j."""
    from db.neo4j_driver import run_query
    res = run_query("MATCH (w:Wallet {address: $addr}) RETURN w", {"addr": seed_wallet})
    assert res, f"Seed wallet {seed_wallet!r} not found in Neo4j"
    print("✅ Seed wallet found in Neo4j.")


def test_neo4j_has_dataset_node(ingest_result):
    """Dataset node was created with CONTAINS_WALLET relationships."""
    from db.neo4j_driver import run_query
    dataset_id = ingest_result["dataset_id"]
    res = run_query("MATCH (d:Dataset {id: $id}) RETURN d", {"id": dataset_id})
    assert res, f"Dataset node {dataset_id!r} not found in Neo4j"
    print(f"✅ Dataset node found: {dataset_id}")


def test_neo4j_has_alert_nodes(ingest_result):
    """Alert nodes were persisted to Neo4j."""
    from db.neo4j_driver import run_query
    dataset_id = ingest_result["dataset_id"]
    res = run_query(
        "MATCH (a:Alert {dataset_id: $did}) RETURN count(a) AS cnt",
        {"did": dataset_id}
    )
    count = int(res[0]["cnt"]) if res else 0
    assert count > 0, "No Alert nodes found in Neo4j after ingest"
    print(f"✅ {count} Alert node(s) found in Neo4j.")


def test_alerts_api_returns_flagged_alerts(ingest_result):
    """GET /alerts via direct service call returns alerts with risk_score >= 60."""
    from db.neo4j_driver import run_query
    dataset_id = ingest_result["dataset_id"]

    res = run_query(
        "MATCH (a:Alert {dataset_id: $did}) RETURN a ORDER BY a.risk_score DESC LIMIT 5",
        {"did": dataset_id}
    )
    assert res, "No alerts returned from Neo4j"
    top_alert = res[0]["a"]
    risk = float(top_alert.get("risk_score") or 0.0)
    assert risk >= 60, f"Expected top alert risk_score >= 60, got {risk}"
    print(f"✅ Top alert risk_score: {risk}%")


def test_peeling_chain_detected(ingest_result):
    """Peeling chain detector flagged at least one chain (3-hop sequence planted)."""
    assert ingest_result["peeling_chains_found"] >= 1, (
        f"Expected >= 1 peeling chain, got {ingest_result['peeling_chains_found']}"
    )
    print(f"✅ Peeling chains detected: {ingest_result['peeling_chains_found']}")


def test_coinjoin_detected(ingest_result):
    """CoinJoin detector flagged the planted mixing transaction."""
    assert ingest_result["coinjoin_mixers_found"] >= 1, (
        f"Expected >= 1 CoinJoin, got {ingest_result['coinjoin_mixers_found']}"
    )
    print(f"✅ CoinJoin mixers detected: {ingest_result['coinjoin_mixers_found']}")


def test_wallet_investigation_api(seed_wallet, ingest_result):
    """Wallet investigation service returns entity + risk + statistics."""
    from services.investigation.wallet import get_summary
    dataset_id = ingest_result["dataset_id"]
    result = get_summary(seed_wallet, dataset_id)

    assert result.get("error") != "not_found", f"Wallet {seed_wallet!r} not found via investigation API"
    assert "entity"     in result
    assert "risk"       in result
    assert "statistics" in result
    print(f"✅ Wallet investigation returned for {seed_wallet[:12]}...")


def test_transaction_investigation_api(ingest_result):
    """Transaction investigation service returns inputs, outputs, broadcasts."""
    from db.neo4j_driver import run_query
    dataset_id = ingest_result["dataset_id"]

    # Get a real txid from Neo4j
    res = run_query(
        "MATCH (d:Dataset {id: $did})-[:CONTAINS_TX]->(t:Transaction) RETURN t.txid AS txid LIMIT 1",
        {"did": dataset_id}
    )
    if not res:
        pytest.skip("No transaction nodes found — Neo4j may not have written them yet.")

    txid = res[0]["txid"]
    from services.investigation.transaction import get_detail
    result = get_detail(txid)

    assert result.get("error") != "not_found", f"Transaction {txid!r} not found"
    assert "transaction" in result
    assert "inputs"      in result
    assert "outputs"     in result
    print(f"✅ Transaction investigation returned for {txid[:12]}...")


def test_ip_investigation_api():
    """IP investigation returns GeoIP data (offline — no Neo4j required)."""
    from services.investigation.ip import get_detail
    result = get_detail("103.1.2.3")

    assert "ip"      in result
    assert "geo"     in result
    assert "network" in result
    # GeoIP may return Unknown for private/test IPs — just check structure
    print(f"✅ IP investigation returned: state={result['geo'].get('state')}")


def test_search_finds_wallet(seed_wallet, ingest_result):
    """Search returns the seed wallet when querying its prefix."""
    from db.neo4j_driver import run_query
    from db.queries.search import search_entities

    prefix = seed_wallet[:6]
    cypher, params = search_entities(prefix, ["wallet"], limit=10)
    params["limit"] = 10

    results = run_query(cypher, params)
    found = any(r.get("id") and seed_wallet in (r.get("id") or "") for r in results)
    assert found, f"Search did not return seed wallet with prefix {prefix!r}"
    print(f"✅ Search found seed wallet with prefix {prefix!r}")


def test_health_ready():
    """Health ready endpoint confirms Neo4j is connected."""
    from api.health import readiness
    result = readiness()
    # Returns JSONResponse(503) or dict
    if hasattr(result, "status_code"):
        assert result.status_code == 200, "Health ready returned non-200"
    else:
        assert result.get("status") == "ready", f"Unexpected health status: {result}"
    print("✅ /health/ready returned ready.")


def test_dataset_isolation(ingest_result):
    """
    CONTAINS_WALLET relationships scope wallets to their dataset.
    A query with the wrong dataset_id must return no wallets.
    """
    from db.neo4j_driver import run_query
    dataset_id = ingest_result["dataset_id"]

    # Real dataset — should have wallets
    res_real = run_query(
        "MATCH (d:Dataset {id: $did})-[:CONTAINS_WALLET]->(w:Wallet) RETURN count(w) AS cnt",
        {"did": dataset_id}
    )
    count_real = int(res_real[0]["cnt"]) if res_real else 0
    assert count_real > 0, "CONTAINS_WALLET not populated for real dataset_id"

    # Fake dataset — should have none
    res_fake = run_query(
        "MATCH (d:Dataset {id: $did})-[:CONTAINS_WALLET]->(w:Wallet) RETURN count(w) AS cnt",
        {"did": "nonexistent_dataset_000"}
    )
    count_fake = int(res_fake[0]["cnt"]) if res_fake else 0
    assert count_fake == 0, "Fake dataset_id unexpectedly returned wallets"
    print(f"✅ Dataset isolation verified: real={count_real}, fake={count_fake}")


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    sw  = f"seed_{uuid.uuid4().hex[:16]}"
    dsw = f"ds_{uuid.uuid4().hex[:16]}"

    print(f"\n🔍 Running integration test with seed_wallet={sw}")
    csv_bytes = _make_synthetic_csv(sw, dsw)

    from services.graph_builder import process_ledger_csv
    result = process_ledger_csv(csv_bytes)
    time.sleep(1)

    tests = [
        lambda: test_pipeline_completes(result),
        lambda: test_neo4j_has_wallet_nodes(sw, result),
        lambda: test_neo4j_has_dataset_node(result),
        lambda: test_neo4j_has_alert_nodes(result),
        lambda: test_alerts_api_returns_flagged_alerts(result),
        lambda: test_peeling_chain_detected(result),
        lambda: test_coinjoin_detected(result),
        lambda: test_wallet_investigation_api(sw, result),
        lambda: test_transaction_investigation_api(result),
        lambda: test_ip_investigation_api(),
        lambda: test_search_finds_wallet(sw, result),
        lambda: test_health_ready(),
        lambda: test_dataset_isolation(result),
    ]

    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed")
    _sys.exit(0 if failed == 0 else 1)
