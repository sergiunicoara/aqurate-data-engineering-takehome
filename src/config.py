from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def load_dotenv(path: Path = Path(".env")) -> None:
    """Load a minimal KEY=VALUE .env file without adding a runtime dependency."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


@dataclass(frozen=True)
class Settings:
    database_path: Path
    database_url: str | None
    require_database_url: bool
    orders_source_url: str
    orders_source_api_key: str
    fx_api_url: str
    timeout_seconds: int

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv()
        database_path = Path(os.getenv("DATABASE_PATH", "data/aqurate.db"))
        database_url = os.getenv("DATABASE_URL", "").strip() or None
        return cls(
            database_path=database_path,
            database_url=database_url,
            require_database_url=os.getenv("REQUIRE_DATABASE_URL", "").lower() in {"1", "true", "yes"},
            orders_source_url=os.getenv("ORDERS_SOURCE_URL", ""),
            orders_source_api_key=os.getenv("ORDERS_SOURCE_API_KEY", ""),
            fx_api_url=os.getenv("FX_API_URL", "https://api.frankfurter.dev/v1").rstrip("/"),
            timeout_seconds=int(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
        )

    def validate_source_credentials(self) -> None:
        if not self.orders_source_url or not self.orders_source_api_key:
            raise ValueError("ORDERS_SOURCE_URL and ORDERS_SOURCE_API_KEY must be set")

    def validate_database_configuration(self) -> None:
        if self.require_database_url and not self.database_url:
            raise ValueError("DATABASE_URL must be set for this run")
