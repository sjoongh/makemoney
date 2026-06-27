# trader/app/config.py
from __future__ import annotations
import os
from dataclasses import dataclass


class ConfigError(RuntimeError):
    """Raised on missing/invalid configuration — fail fast at startup."""


@dataclass(frozen=True)
class AppConfig:
    kis_app_key: str
    kis_app_secret: str
    kis_account: str
    paper: bool = True

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Build from environment, validating fail-fast.

        Required: KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT (non-empty).
        KIS_PAPER defaults to "1" (paper); only the exact string "0" disables it.

        Note: live ORDER submission has a separate, stronger gate
        (trader.app.run_daily.live_allowed) and the daily runner targets the
        paper endpoint by default — this validation is config sanity only, it
        does NOT authorize live trading.
        """
        key = os.environ.get("KIS_APP_KEY", "").strip()
        secret = os.environ.get("KIS_APP_SECRET", "").strip()
        account = os.environ.get("KIS_ACCOUNT", "").strip()

        missing = [n for n, v in (("KIS_APP_KEY", key),
                                  ("KIS_APP_SECRET", secret),
                                  ("KIS_ACCOUNT", account)) if not v]
        if missing:
            raise ConfigError(
                f"missing/empty required env var(s): {', '.join(missing)}. "
                "Set them (e.g. in a gitignored .env) before running."
            )

        paper = os.environ.get("KIS_PAPER", "1").strip() != "0"
        return cls(key, secret, account, paper)
