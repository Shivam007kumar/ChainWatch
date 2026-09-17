from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    neo4j_uri: str = "neo4j+s://a1e86c76.databases.neo4j.io"
    neo4j_user: Optional[str] = None
    neo4j_username: str = "a1e86c76"
    neo4j_password: str = "oi81nq2AOzIXhkfjJtjv0RLDQ5JMaw70fynlU2c9b2Q"
    neo4j_database: str = "a1e86c76"
    correlation_window_seconds: int = 30
    correlation_tau: float = 8.0
    env: str = "dev"

    @property
    def auth_user(self) -> str:
        return self.neo4j_user or self.neo4j_username or "neo4j"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# MaxMind DB and CSV paths
CITY_DB_PATH = BASE_DIR.parent / "GeoLite2-City_20260904" / "GeoLite2-City.mmdb"
ASN_DB_PATH = BASE_DIR.parent / "GeoLite2-ASN_20260904" / "GeoLite2-ASN.mmdb"
ALT_CITY_DB_PATH = BASE_DIR / "database" / "GeoIP-City.mmdb"
ALT_ASN_DB_PATH = BASE_DIR / "database" / "GeoIP-ASN.mmdb"
LOCATION_CSV_PATH = BASE_DIR.parent / "IP_Address.csv"
ASN_CSV_PATH = BASE_DIR.parent / "dbip-asn-lite-2026-09.csv"
