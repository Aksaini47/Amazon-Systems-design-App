"""Central configuration — single source of truth for env vars.

Loads `.env` from the project root via python-dotenv, then exposes a
strongly-typed `Settings` object. All other modules import `settings`
from here — never read `os.environ` directly.
"""
from __future__ import annotations

import os
import socket
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_runner_id() -> str:
    """Hostname-based runner ID. Overridable via env."""
    return os.environ.get("MAHIKA_RUNNER_ID") or socket.gethostname()


class Settings(BaseSettings):
    """All Mahika runtime configuration. Loaded from `.env` at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MAHIKA_",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Postgres ─────────────────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "mahika"
    db_user: str = "mahika"
    db_password: str = ""

    @property
    def db_dsn(self) -> str:
        """SQLAlchemy URL for psycopg v3 driver.

        Note: uses the `postgresql+psycopg://` dialect URL so SQLAlchemy
        picks psycopg 3 (the binary build we depend on) instead of the
        legacy psycopg2 default. See pyproject.toml `psycopg[binary]`.
        """
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ─── Storage paths ────────────────────────────────────────────────
    storage_root: Path = Path("D:/Mahika")

    @property
    def orders_dir(self) -> Path:
        return self.storage_root / "orders"

    @property
    def sync_inbox_dir(self) -> Path:
        return self.storage_root / "sync_inbox"

    @property
    def processed_dir(self) -> Path:
        return self.storage_root / "processed"

    @property
    def backups_dir(self) -> Path:
        return self.storage_root / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.storage_root / "logs"

    @property
    def reports_inbox_dir(self) -> Path:
        return self.storage_root / "reports" / "inbox"

    @property
    def reports_archive_dir(self) -> Path:
        return self.storage_root / "reports" / "archive"

    @property
    def reports_analysis_dir(self) -> Path:
        return self.storage_root / "reports" / "analysis"

    # ─── Amazon SP-API ────────────────────────────────────────────────
    sp_api_refresh_token: str = ""
    sp_api_lwa_client_id: str = ""
    sp_api_lwa_client_secret: str = ""
    sp_api_role_arn: str = ""
    sp_api_region: str = "eu-west-1"        # India seller account → EU region per SP-API docs
    sp_api_marketplace_id: str = "A21TJRUUN4KGV"  # Amazon.in marketplace
    # True while using Mahika V1 sandbox token (▼ → Create Token → Sandbox Testing).
    # Set false after production app authorize + production refresh token in .env.
    sp_api_sandbox: bool = True

    @property
    def sp_api_configured(self) -> bool:
        """True when at minimum the refresh + LWA creds are filled."""
        return all([
            self.sp_api_refresh_token,
            self.sp_api_lwa_client_id,
            self.sp_api_lwa_client_secret,
        ])

    # ─── Telegram bot ─────────────────────────────────────────────────
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    # ─── Runner identity ──────────────────────────────────────────────
    runner_id: str = Field(default_factory=_default_runner_id)

    # ─── Operating mode ───────────────────────────────────────────────
    mode: Literal["shadow", "live", "manual"] = "shadow"

    # ─── Cockpit (Phase 6) ────────────────────────────────────────────
    # FastAPI dashboard runs locally on the active runner. Single-user token
    # auth — Sir sets the token in `.env`, then visits http://localhost:{port}/
    # and pastes it on the login page. The cockpit is NEVER exposed publicly.
    cockpit_token: str = ""           # session token Sir uses to log in
    cockpit_port: int = 8765          # high port to avoid conflicts
    cockpit_host: str = "127.0.0.1"   # localhost only — never bind 0.0.0.0
    cockpit_session_secret: str = ""  # auto-generated on first boot if empty

    # ─── Exception tracking ──────────────────────────────────────────
    sentry_dsn: str = ""


# Singleton — import this in every other module.
settings = Settings()

# python-amazon-sp-api reads AWS_ENV at first import of sp_api.base.marketplaces.
# Must be set before any Orders/Finances/Reports client is constructed.
import os as _os

if settings.sp_api_sandbox:
    _os.environ["AWS_ENV"] = "SANDBOX"
else:
    _os.environ.setdefault("AWS_ENV", "PRODUCTION")
