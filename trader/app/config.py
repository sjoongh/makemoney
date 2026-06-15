# trader/app/config.py
from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class AppConfig:
    kis_app_key: str; kis_app_secret: str; kis_account: str; paper: bool = True

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(os.environ["KIS_APP_KEY"], os.environ["KIS_APP_SECRET"],
                   os.environ["KIS_ACCOUNT"], os.environ.get("KIS_PAPER","1")=="1")
