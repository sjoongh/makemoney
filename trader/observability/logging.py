from __future__ import annotations
import structlog

def get_logger(name: str = "trader"):
    return structlog.get_logger(name)
