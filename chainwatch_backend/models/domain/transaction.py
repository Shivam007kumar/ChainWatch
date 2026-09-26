"""
models/domain/transaction.py
─────────────────────────────
CanonicalTransaction — the single internal representation every downstream
service (feature matrix, Neo4j writer, evidence aggregator) consumes.

Every input format (CSV today, JSON/XML in future) is parsed into
CanonicalTransaction before touching ML or Neo4j. This eliminates
scattered row["field"] dict access across the pipeline.

Populated in two passes:
  Pass 1 — ingestion/parser.py     : core identity + blockchain + network fields
  Pass 2 — services/geoip enrichment: src_geo, dst_geo
  Pass 3 — correlation pass         : broadcast_confidence
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class GeoInfo:
    """GeoIP enrichment result for a single IP address."""
    state:     str   = "Unknown"
    city:      str   = "Unknown"
    country:   str   = "Unknown"
    asn:       str   = "N/A"
    org:       str   = "N/A"
    latitude:  Optional[float] = None
    longitude: Optional[float] = None
    # Provenance — which source answered this lookup
    source:    str   = "unknown"   # "maxmind" | "csv_fallback" | "unknown"
    fallback:  bool  = False


@dataclass
class CanonicalTransaction:
    """
    Normalised internal representation of one Bitcoin network observation.

    Fields are separated into three groups:
      - Identity / blockchain: txid, timestamp, amounts, script, fee
      - Network layer: src/dst IP, ports
      - Derived (populated after enrichment): geo, confidence, balance_delta
    """

    # ── Identity ──────────────────────────────────────────────────────────────
    txid:        str
    timestamp:   datetime
    dataset_id:  str = ""

    # ── Blockchain layer ──────────────────────────────────────────────────────
    input_addresses:  list[str]   = field(default_factory=list)
    output_addresses: list[str]   = field(default_factory=list)
    input_amounts:    list[float] = field(default_factory=list)
    output_amounts:   list[float] = field(default_factory=list)
    fee:              float = 0.0
    script_type:      str   = "P2PKH"

    # ── Network layer ─────────────────────────────────────────────────────────
    src_ip:   str = ""
    dst_ip:   str = ""
    src_port: int = 0
    dst_port: int = 8333

    # ── Derived: enriched after GeoIP pass ───────────────────────────────────
    src_geo: Optional[GeoInfo] = None
    dst_geo: Optional[GeoInfo] = None

    # ── Derived: set after broadcast correlation pass ─────────────────────────
    broadcast_confidence: float = 1.0

    # ── Derived: computed from amounts ───────────────────────────────────────
    # balance_delta = sum(input_amounts) - sum(output_amounts) - fee
    # Negative value indicates a balance violation (inputs < outputs + fee).
    balance_delta: float = 0.0

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def input_volume_btc(self) -> float:
        return sum(self.input_amounts)

    @property
    def output_volume_btc(self) -> float:
        return sum(self.output_amounts)

    @property
    def fee_ratio(self) -> float:
        """fee / input_volume — 0.0 if no inputs."""
        vol = self.input_volume_btc
        return round(self.fee / vol, 8) if vol > 0 else 0.0

    @property
    def has_balance_violation(self) -> bool:
        return self.balance_delta < -0.0001

    def compute_balance_delta(self) -> "CanonicalTransaction":
        """Populate balance_delta from amounts. Returns self for chaining."""
        self.balance_delta = self.input_volume_btc - self.output_volume_btc - self.fee
        return self


@dataclass
class RejectedRow:
    """
    Records a row that was rejected during validation.
    Returned by ingestion/validator.py alongside valid CanonicalTransactions.
    """
    row_index:   int
    txid:        str
    reason:      str
    raw_snippet: str = ""   # first 120 chars of the raw CSV row for debugging
