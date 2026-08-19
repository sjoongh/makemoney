# trader/data/naver_flows.py
"""RESEARCH ONLY — per-stock daily investor flows from Naver Finance (free).

Free-data expansion R7 (KR flows). Naver's frgn page carries ~16y of daily
기관/외국인 net-trading per stock (KIS's inquire-investor API returns only 30
trading days — used for the daily forward path; Naver fills the backfill).

Point-in-time note: each row is the flow OF that trading day, published after
close → usable from the NEXT trading day (effective-date rule downstream,
same as event signals; enforce with embargo, not here).

Pure parsing separated from HTTP. Individual (개인) flows are NOT on this
page; signals must be defined on 기관/외국인 only.

NEVER import from live/paper trading or the backtest/live parity path.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import httpx
import pandas as pd

FRGN_URL = "https://finance.naver.com/item/frgn.naver"
NAVER_HEADERS = {"User-Agent": "Mozilla/5.0 (makemoney-research)"}

REQUIRED_FIELDS = ("symbol", "date", "close", "volume", "inst_net", "frgn_net")

_ROW_RE = re.compile(
    r'<span class="tah p10 gray03">(\d{4}\.\d{2}\.\d{2})</span>(.*?)</tr>',
    re.DOTALL,
)
_VAL_RE = re.compile(r'<span class="tah[^"]*">([^<]+)</span>')


def _num(raw: str, date: str) -> float:
    s = raw.strip().replace(",", "").replace("%", "").replace("+", "")
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"malformed numeric {raw!r} in row {date}") from None


def parse_naver_frgn(html: str) -> list[dict]:
    """Parse one frgn page → rows (newest first, as served).

    Row layout: 종가|전일비|등락률|거래량|기관순매매|외인순매매|외인보유주수|외인보유율.
    """
    out: list[dict] = []
    for m in _ROW_RE.finditer(html):
        date_raw, rest = m.group(1), m.group(2)
        vals = _VAL_RE.findall(rest)
        if len(vals) < 8:
            continue  # summary/decoration row, not a data row
        date = date_raw.replace(".", "-")
        out.append(
            {
                "date": date,
                "close": _num(vals[0], date_raw),
                "volume": int(_num(vals[3], date_raw)),
                "inst_net": int(_num(vals[4], date_raw)),
                "frgn_net": int(_num(vals[5], date_raw)),
                "frgn_held": int(_num(vals[6], date_raw)),
                "frgn_ratio": _num(vals[7], date_raw),
            }
        )
    return out


def fetch_frgn_page(code: str, page: int, timeout: float = 20.0) -> list[dict]:
    """Fetch + parse one frgn page for one 6-digit KRX code."""
    resp = httpx.get(
        FRGN_URL, params={"code": code, "page": page},
        headers=NAVER_HEADERS, timeout=timeout,
    )
    resp.raise_for_status()
    return parse_naver_frgn(resp.text)


# ---------------------------------------------------------------------------
# flow store — parquet + manifest, dedupe by (symbol, date), newest write wins
# ---------------------------------------------------------------------------


def load_flows(path: str | Path) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    return pd.read_parquet(p).to_dict("records")


def _content_hash(rows: list[dict]) -> str:
    canon = sorted(json.dumps(r, sort_keys=True, ensure_ascii=False) for r in rows)
    h = hashlib.sha256()
    for line in canon:
        h.update(line.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def save_flows(path: str | Path, rows: list[dict], created_ts: str) -> int:
    """Merge rows into the flow table; returns total rows stored."""
    for r in rows:
        missing = [f for f in REQUIRED_FIELDS if str(r.get(f, "")).strip() == ""]
        if missing:
            raise ValueError(f"flow row missing {missing[0]}: {r!r}")
    merged = {(r["symbol"], r["date"]): dict(r) for r in load_flows(path)}
    for r in rows:
        merged[(r["symbol"], r["date"])] = dict(r)
    final = sorted(merged.values(), key=lambda r: (r["date"], r["symbol"]))
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(final).to_parquet(p, index=False)
    manifest = {
        "dataset_id": p.stem,
        "created_ts": created_ts,
        "n_rows": len(final),
        "content_hash": _content_hash(final),
    }
    Path(str(p) + ".manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return len(final)
