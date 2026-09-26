"""
services/investigation/ip.py
──────────────────────────────
Business logic for GET /investigations/ip/{ip}.
"""
from __future__ import annotations

import logging
from typing import Optional

from db.neo4j_driver import run_query
from db.queries import get_ip_detail
from services.geoip import lookup_ip

logger = logging.getLogger("chainwatch.investigation.ip")


def get_detail(ip_address: str, dataset_id: Optional[str] = None) -> dict:
    """
    Full IP investigation including GeoIP (with provenance), ASN,
    broadcast observation history, and linked wallets/transactions.
    """
    # Always resolve GeoIP live — authoritative, no Neo4j required
    geo_raw  = lookup_ip(ip_address)
    geo_source = "maxmind" if geo_raw.get("_source") == "maxmind" else (
        "csv_fallback" if geo_raw.get("_source") == "csv" else "unknown"
    )

    geo = {
        "city":      geo_raw.get("city",      "Unknown"),
        "state":     geo_raw.get("state",     "Unknown"),
        "country":   geo_raw.get("country",   "Unknown"),
        "latitude":  geo_raw.get("latitude"),
        "longitude": geo_raw.get("longitude"),
        "source":    {
            "provider": "MaxMind GeoLite2" if "maxmind" in geo_source else "IP_Address.csv",
            "fallback": geo_source == "csv_fallback",
        },
    }
    network = {
        "asn":          geo_raw.get("asn",  "N/A"),
        "organization": geo_raw.get("org",  "N/A"),
    }

    # Neo4j — observation history and linked entities
    try:
        results = run_query(*get_ip_detail(ip_address, dataset_id))
    except Exception as exc:
        logger.warning(f"Neo4j unavailable for IP {ip_address}: {exc}")
        return _minimal_response(ip_address, geo, network)

    if not results or results[0].get("ip") is None:
        return _minimal_response(ip_address, geo, network)

    row   = results[0]
    ip_n  = row["ip"]

    # Prefer Neo4j geo over live lookup when both available
    # (Neo4j may have been enriched with a more specific source at ingest time)
    if ip_n.get("state") and ip_n["state"] != "Unknown":
        geo["state"] = ip_n["state"]
    if ip_n.get("asn") and ip_n["asn"] != "N/A":
        network["asn"] = ip_n["asn"]
    if ip_n.get("org") and ip_n["org"] != "N/A":
        network["organization"] = ip_n["org"]

    observations = []
    for obs in (row.get("observations") or []):
        if not obs or not obs.get("txid"):
            continue
        observations.append({
            "txid":        obs["txid"],
            "timestamp":   str(obs.get("timestamp", "")),
            "confidence":  round(float(obs.get("confidence") or 1.0), 4),
        })
    observations.sort(key=lambda o: float(o.get("confidence") or 0), reverse=True)

    return {
        "ip":           ip_address,
        "geo":          geo,
        "network":      network,
        "observations": observations,
        "linked_wallets":      list(row.get("linked_wallets") or [])[:50],
        "linked_transactions": list(row.get("linked_txids")   or [])[:50],
    }


def _minimal_response(ip: str, geo: dict, network: dict) -> dict:
    return {
        "ip":           ip,
        "geo":          geo,
        "network":      network,
        "observations": [],
        "linked_wallets":      [],
        "linked_transactions": [],
        "_note": "Neo4j unavailable — graph data not included.",
    }
