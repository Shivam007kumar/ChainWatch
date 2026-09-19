from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # ── Neo4j connection ──────────────────────────────────────────────────────
    # All credentials must be supplied via .env — no defaults are set here so a
    # misconfigured deployment fails loudly instead of silently using a stale
    # cloud instance.
    neo4j_uri:      str           = "bolt://localhost:7687"   # local docker default
    neo4j_user:     Optional[str] = None
    neo4j_username: str           = "neo4j"
    neo4j_password: str           = ""          # must be set in .env
    neo4j_database: str           = "neo4j"

    # ── Broadcast correlation engine ─────────────────────────────────────────
    correlation_window_seconds: int   = 30
    correlation_tau:            float = 8.0

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
CITY_DB_PATH     = BASE_DIR.parent / "GeoLite2-City_20260904"  / "GeoLite2-City.mmdb"
ASN_DB_PATH      = BASE_DIR.parent / "GeoLite2-ASN_20260904"   / "GeoLite2-ASN.mmdb"
ALT_CITY_DB_PATH = BASE_DIR / "database" / "GeoIP-City.mmdb"
ALT_ASN_DB_PATH  = BASE_DIR / "database" / "GeoIP-ASN.mmdb"
LOCATION_CSV_PATH = BASE_DIR.parent / "IP_Address.csv"
ASN_CSV_PATH      = BASE_DIR.parent / "dbip-asn-lite-2026-09.csv"
