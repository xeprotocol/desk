from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://desk:desk@localhost:5432/desk", alias="DATABASE_URL"
    )
    xe_node_url: str = Field(default="https://ldn.core.test.network", alias="XE_NODE_URL")
    public_base_url: str = Field(default="http://localhost:8010", alias="PUBLIC_BASE_URL")
    bounty_host: str = Field(default="", alias="DESK_BOUNTY_HOST")
    support_host: str = Field(default="", alias="DESK_SUPPORT_HOST")
    webauthn_rp_id: str = Field(default="", alias="WEBAUTHN_RP_ID")
    webauthn_rp_name: str = Field(default="XE Desk", alias="WEBAUTHN_RP_NAME")
    config_dir: Path = Field(default=Path("config"), alias="DESK_CONFIG_DIR")
    signer_keyfile: Path = Field(default=Path("secrets/signer.json"), alias="DESK_SIGNER_KEYFILE")
    signer_passphrase: str = Field(default="", alias="DESK_SIGNER_PASSPHRASE")
    blob_dir: Path = Field(default=Path("blobs"), alias="DESK_BLOB_DIR")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_webhook_secret: str = Field(default="", alias="GITHUB_WEBHOOK_SECRET")
    github_bot_login: str = Field(default="", alias="GITHUB_BOT_LOGIN")  # the account GITHUB_TOKEN belongs to
    # Links for `internal_ref`. The tracker is xeprotocol/core (private; the link only resolves for the team).
    internal_tracker_url: str = Field(
        default="https://github.com/xeprotocol/core/issues/{ref}", alias="INTERNAL_TRACKER_URL"
    )
    internal_tracker_faucet_url: str = Field(
        default="https://github.com/xeprotocol/faucet/issues/{ref}", alias="INTERNAL_TRACKER_FAUCET_URL"
    )
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="desk@xe.network", alias="SMTP_FROM")
    git_commit: str = Field(default=os.environ.get("DESK_GIT_COMMIT", "unknown"), alias="GIT_COMMIT")
    log_level: str = Field(default="info", alias="LOG_LEVEL")
    role: str = Field(default="api", alias="DESK_ROLE")

    @property
    def sync_database_url(self) -> str:
        return self.database_url.replace("+asyncpg", "+psycopg")

    @property
    def public_host(self) -> str:
        return urlsplit(self.public_base_url).hostname or "localhost"

    @property
    def scheme(self) -> str:
        return urlsplit(self.public_base_url).scheme or "https"

    @property
    def hosts(self) -> dict[str, str]:
        """Front doors by host name. Both default to the public host when unset (single-host deployment)."""
        return {
            "bounty": self.bounty_host or self.public_host,
            "support": self.support_host or self.public_host,
        }

    @property
    def rp_id(self) -> str:
        """WebAuthn relying-party id: configured, else the registrable suffix shared by the hosts."""
        if self.webauthn_rp_id:
            return self.webauthn_rp_id
        hosts = list(self.hosts.values())
        parts = [h.split(".") for h in hosts]
        common: list[str] = []
        for labels in zip(*[p[::-1] for p in parts]):
            if len(set(labels)) == 1:
                common.append(labels[0])
            else:
                break
        rp = ".".join(reversed(common)) if common else self.public_host
        return rp if rp.count(".") >= 1 or rp == "localhost" else self.public_host

    @property
    def origins(self) -> list[str]:
        """Origins passkeys may be used from: every front door, plus the public base."""
        out = [f"{self.scheme}://{h}" for h in self.hosts.values()]
        base = self.public_base_url.rstrip("/")
        if base not in out:
            out.append(base)
        return out

    def internal_url(self, ref: str) -> str:
        """Link for an internal ticket reference such as `#1064` or `faucet#10`; empty when unconfigured."""
        if not ref:
            return ""
        if ref.startswith("faucet#"):
            tpl = self.internal_tracker_faucet_url
            n = ref.split("#", 1)[1]
        else:
            tpl = self.internal_tracker_url
            n = ref.lstrip("#")
        return tpl.replace("{ref}", n) if tpl and n.isdigit() else ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
