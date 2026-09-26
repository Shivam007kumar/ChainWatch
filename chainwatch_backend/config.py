from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # ── Neo4j connection ──────────────────────────────────────────────────────
    # Credentials must come from .env — no hardcoded URIs or passwords here.
    # Default URI points to local docker-compose Neo4j (bolt://localhost:7687).
    # Empty password causes loud auth failure on startup, which is intentional.
    neo4j_uri:      str           = "bolt://localhost:7687"
    neo4j_user:     Optional[str] = None
    neo4j_username: str           = "neo4j"
    neo4j_password: str           = ""          # must be set in .env
    neo4j_database: str           = "neo4j"

    # ── Broadcast correlation engine ─────────────────────────────────────────
    correlation_window_seconds: int   = 30
    correlation_tau:            float = 8.0

    # ── Investigation / graph limits ─────────────────────────────────────────
    # Tune these in .env for larger datasets.
    max_investigation_hops:    int = 5
    max_graph_nodes:           int = 500
    max_graph_edges:           int = 1000
    max_page_size:             int = 100
    # Maximum transactions written to Neo4j and the JSON graph per ingest.
    # Default covers 10,000-row showcase datasets with headroom.
    # Raise in .env for production-scale datasets.
    max_graph_transactions:    int = 15_000

    # ── API security ─────────────────────────────────────────────────────────
    # Required on POST /ingest, POST /clear, DELETE /clear via X-API-Key header.
    # Change in .env for production — do not leave as default in deployed systems.
    api_key: str = "chainwatch-local"

    # ── Ingest limits ────────────────────────────────────────────────────────
    max_upload_bytes: int = 52_428_800   # 50 MB

    env: str = "dev"

    @property
    def auth_user(self) -> str:
        return self.neo4j_user or self.neo4j_username or "neo4j"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

# ── GeoIP / ASN database paths ────────────────────────────────────────────────
CITY_DB_PATH      = BASE_DIR.parent / "GeoLite2-City_20260904" / "GeoLite2-City.mmdb"
ASN_DB_PATH       = BASE_DIR.parent / "GeoLite2-ASN_20260904"  / "GeoLite2-ASN.mmdb"
ALT_CITY_DB_PATH  = BASE_DIR / "database" / "GeoIP-City.mmdb"
ALT_ASN_DB_PATH   = BASE_DIR / "database" / "GeoIP-ASN.mmdb"
LOCATION_CSV_PATH = BASE_DIR.parent / "IP_Address.csv"
ASN_CSV_PATH      = BASE_DIR.parent / "dbip-asn-lite-2026-09.csv"
