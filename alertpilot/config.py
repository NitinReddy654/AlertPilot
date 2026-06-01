from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "AlertPilot"
    environment: str = "development"
    database_path: str = "data/alertpilot.db"
    token_secret: str = "dev-only-change-me"
    token_ttl_seconds: int = 3600
    bootstrap_email: str = "admin@alertpilot.local"
    bootstrap_password: str = "changeme"
    log_level: str = "INFO"
    enable_redis: bool = False
    redis_url: str = "redis://localhost:6379/0"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=os.getenv("ALERTPILOT_ENV", "development"),
            database_path=os.getenv("ALERTPILOT_DB_PATH", "data/alertpilot.db"),
            token_secret=os.getenv("ALERTPILOT_TOKEN_SECRET", "dev-only-change-me"),
            token_ttl_seconds=int(os.getenv("ALERTPILOT_TOKEN_TTL_SECONDS", "3600")),
            bootstrap_email=os.getenv("ALERTPILOT_BOOTSTRAP_EMAIL", "admin@alertpilot.local"),
            bootstrap_password=os.getenv("ALERTPILOT_BOOTSTRAP_PASSWORD", "changeme"),
            log_level=os.getenv("ALERTPILOT_LOG_LEVEL", "INFO"),
            enable_redis=os.getenv("ALERTPILOT_ENABLE_REDIS", "0") == "1",
            redis_url=os.getenv("ALERTPILOT_REDIS_URL", "redis://localhost:6379/0"),
        )

    def ensure_runtime_dirs(self) -> None:
        db_path = Path(self.database_path)
        if str(db_path) != ":memory:":
            db_path.parent.mkdir(parents=True, exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

