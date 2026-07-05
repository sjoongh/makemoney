# trader/app/status_dashboard.py
"""Unified status for the makemoney paper system — one place, no scattered logs.

`gather_status()` collects EVERYTHING (account, performance, job health, data
freshness, recent fills) into one plain dict.  `render_terminal()` prints a
single clean screen; `render_html()` writes a self-contained status.html you can
keep open in a browser (auto-refreshes) — the "상태바 다른 곳에서 확인" ask.

Read-only: never places orders.  Rendering is pure (takes a status dict), so it
is unit-tested without touching KIS.
"""
from __future__ import annotations

import html
import json
import os
from datetime import datetime, timezone

from trader.app.run_performance import (
    benchmark_return,
    inception,
    inception_usd_fx,
    load_track,
    pct,
)

# component -> (label, stale-after hours)  — mirrors run_healthcheck expectations
JOBS = {
    "accumulator": ("데이터 누적", 30.0),
    "forward_record": ("포워드 레코더", 30.0),
    "beta_kis_kr": ("KR 방어베타 (KODEX)", 80.0),
    "beta_kis_us": ("US 방어베타 (SPY)", 80.0),
}


def _age_hours(iso: str, now: datetime) -> float:
    try:
        return (now - datetime.fromisoformat(iso)).total_seconds() / 3600.0
    except (ValueError, TypeError):
        return float("inf")


def gather_status(
    *,
    kis=None,
    heartbeat_path: str = ".heartbeat.json",
    manifest_path: str = "research_data/_manifest.json",
    track_path: str = "beta_kis_track.jsonl",
    now: datetime | None = None,
    with_benchmarks: bool = True,
) -> dict:
    """Collect the full system status into one dict. Every section degrades
    gracefully (records an error string) so one failure never blanks the rest."""
    now = now or datetime.now(tz=timezone.utc)
    status: dict = {"as_of": now.isoformat(), "sections": {}}

    # ── account + performance ────────────────────────────────────────────
    # KIS paper balance endpoints have no internal retry and 500 on bursts, so
    # tolerate a transient failure here before flipping the dashboard red.
    acct: dict = {}
    for attempt in range(3):
        try:
            if kis is None:
                from trader.app.run_daily import build_kis_client, _load_dotenv
                if "KIS_APP_KEY" not in os.environ:
                    _load_dotenv()
                kis = build_kis_client()
            snap = kis.account_snapshot()
            fx = kis.usd_krw_rate(default=-1.0)
            usd_fx = fx if fx > 0 else 0.0
            has_us = any(m == "NASDAQ" for (m, _t) in snap["positions"])
            # If FX is down while holding USD names, equity CANNOT be computed
            # (nass already netted the phantom overseas cost; without ovr_val we
            # would report a grossly understated equity). Report it as unknown.
            fx_unknown = has_us and usd_fx <= 0
            ovr_val = sum(q * snap["marks"].get((m, t), 0.0) * usd_fx
                          for (m, t), q in snap["positions"].items() if m == "NASDAQ")
            equity = None if fx_unknown else snap["nass_krw"] - snap["ovr_purchase_krw"] + ovr_val
            positions = []
            for (m, t), q in sorted(snap["positions"].items()):
                mark = snap["marks"].get((m, t), 0.0)
                val = q * mark * (usd_fx if m == "NASDAQ" else 1.0)
                positions.append({"market": m, "ticker": t, "qty": q, "mark": mark,
                                  "value_krw": val,
                                  "weight": val / equity if equity else 0.0})
            acct = {"equity_krw": equity, "cash_krw": snap["cash_krw"],
                    "cash_weight": snap["cash_krw"] / equity if equity else 0.0,
                    "fx": fx, "fx_unknown": fx_unknown, "positions": positions}
            break
        except Exception as exc:  # noqa: BLE001 — status must never crash
            acct = {"error": f"{type(exc).__name__}: {exc}"}
            if attempt < 2:
                import time
                time.sleep(1.5 * (attempt + 1))   # 1.5s, 3s backoff
    status["sections"]["account"] = acct

    # ── performance since clean-era inception ────────────────────────────
    perf: dict = {}
    track = load_track(track_path)
    base = inception(track)
    if base and acct.get("equity_krw"):
        perf["since"] = base["as_of"][:10]
        perf["inception_equity"] = base["equity_krw"]
        perf["strategy_return"] = pct(acct["equity_krw"], base["equity_krw"])
        if with_benchmarks:
            base_fx = inception_usd_fx(track)
            latest_fx = acct.get("fx") if acct.get("fx", 0) > 0 else None
            for label, sym, to_krw in (("SPY", "SPY", True), ("KODEX200", "069500.KS", False)):
                br = benchmark_return(sym, base["as_of"], to_krw=to_krw,
                                      base_fx=base_fx, latest_fx=latest_fx)
                if br is not None:
                    perf.setdefault("benchmarks", {})[label] = br
    status["sections"]["performance"] = perf

    # ── job health (dead-man's switch view) ──────────────────────────────
    jobs = []
    try:
        from trader.live import heartbeat as hb
        beats = hb.load(heartbeat_path)
    except Exception:  # noqa: BLE001
        beats = {}
    for comp, (label, stale_h) in JOBS.items():
        ts = beats.get(comp)
        age = _age_hours(ts, now) if ts else float("inf")
        jobs.append({"component": comp, "label": label,
                     "last": ts, "age_hours": age,
                     "ok": age <= stale_h, "never": ts is None})
    status["sections"]["jobs"] = jobs

    # ── data freshness ───────────────────────────────────────────────────
    data: dict = {}
    try:
        with open(manifest_path, encoding="utf-8") as fh:
            man = json.load(fh)
        last_dates = [v.get("last_date") for v in man.values() if v.get("last_date")]
        ok = sum(1 for v in man.values() if v.get("status") == "ok")
        data = {"symbols": len(man), "ok": ok,
                "newest": max(last_dates) if last_dates else None,
                "oldest": min(last_dates) if last_dates else None}
    except Exception as exc:  # noqa: BLE001
        data = {"error": f"{type(exc).__name__}: {exc}"}
    status["sections"]["data"] = data

    # ── recent fills ─────────────────────────────────────────────────────
    fills = [{"when": r["as_of"][:16], "market": r["market"], "side": r["side"],
              "qty": r["qty"], "etf": r["etf"], "odno": r["submitted_odno"]}
             for r in track if r.get("submitted_odno")]
    status["sections"]["fills"] = fills[-8:]

    # ── overall health rollup ────────────────────────────────────────────
    problems = []
    if acct.get("error"):
        problems.append("account unreadable")
    elif acct.get("fx_unknown"):
        problems.append("FX unavailable (equity unknown)")
    # A monitored job that never emitted a heartbeat is a problem too (MISSING),
    # matching run_healthcheck's default — a mis-keyed/dead job must not show green.
    problems += [f"{j['label']} " + ("MISSING" if j["never"] else "STALE")
                 for j in jobs if not j["ok"]]
    if data.get("error"):
        problems.append("data manifest unreadable")
    status["healthy"] = not problems
    status["problems"] = problems
    return status


# ---------------------------------------------------------------------------
# Renderers (pure — take the status dict)
# ---------------------------------------------------------------------------

def _krw(v) -> str:
    return f"{v:,.0f}" if isinstance(v, (int, float)) else "—"


def render_terminal(s: dict) -> str:
    L = []
    dot = "🟢" if s["healthy"] else "🔴"
    L.append("=" * 60)
    L.append(f" {dot} MAKEMONEY 상태  ·  {s['as_of'][:16].replace('T', ' ')} UTC")
    L.append("=" * 60)
    if s["problems"]:
        L.append(" ⚠️  " + " | ".join(s["problems"]))
        L.append("-" * 60)

    a = s["sections"]["account"]
    if a.get("error"):
        L.append(f" 계좌: 읽기 실패 — {a['error']}")
    elif a.get("fx_unknown"):
        L.append(" 자산  unknown (FX 조회 실패 — USD 평가 불가)")
        for p in a["positions"]:
            L.append(f"   · {p['ticker']:<7}[{p['market']}] {p['qty']:>4} @ {p['mark']:>10,.2f}")
    else:
        L.append(f" 자산  {_krw(a['equity_krw'])} KRW   (현금 {a['cash_weight']:.0%})")
        for p in a["positions"]:
            L.append(f"   · {p['ticker']:<7}[{p['market']}] {p['qty']:>4} @ "
                     f"{p['mark']:>10,.2f}  →  {_krw(p['value_krw'])} KRW ({p['weight']:.0%})")

    perf = s["sections"]["performance"]
    if perf.get("strategy_return") is not None:
        L.append("-" * 60)
        L.append(f" 성과 (since {perf['since']})   전략 {perf['strategy_return']:+.2%}")
        for k, v in perf.get("benchmarks", {}).items():
            L.append(f"   벤치 {k:<9} {v:+.2%}")

    L.append("-" * 60)
    L.append(" 작업 상태 (dead-man switch)")
    for j in s["sections"]["jobs"]:
        mark = "🟢" if j["ok"] else ("⚪️" if j["never"] else "🔴")
        age = "없음" if j["never"] else f"{j['age_hours']:.0f}h 전"
        L.append(f"   {mark} {j['label']:<22} {age}")

    d = s["sections"]["data"]
    L.append("-" * 60)
    if d.get("error"):
        L.append(f" 데이터: {d['error']}")
    else:
        L.append(f" 데이터  {d['ok']}/{d['symbols']} ok · 최신 {d['newest']}")

    fills = s["sections"]["fills"]
    if fills:
        L.append("-" * 60)
        L.append(f" 최근 체결 ({len(fills)})")
        for f in fills[-5:]:
            L.append(f"   {f['when']}  {f['market']} {f['side']} {f['qty']} {f['etf']}")
    L.append("=" * 60)
    return "\n".join(L)


def render_html(s: dict) -> str:
    esc = html.escape
    dot = "#16a34a" if s["healthy"] else "#dc2626"
    label = "정상" if s["healthy"] else "점검 필요"
    a = s["sections"]["account"]
    perf = s["sections"]["performance"]

    def card(title, body):
        return f'<section class="card"><h2>{esc(title)}</h2>{body}</section>'

    # account card
    if a.get("error"):
        acc_body = f'<p class="err">읽기 실패 — {esc(str(a["error"]))}</p>'
    elif a.get("fx_unknown"):
        acc_body = ('<p class="big">unknown</p>'
                    '<p class="sub">FX 조회 실패 — USD 평가 불가</p>')
    else:
        rows = "".join(
            f'<tr><td>{esc(p["ticker"])} <span class="mkt">{esc(p["market"])}</span></td>'
            f'<td class="num">{p["qty"]:,}</td><td class="num">{p["mark"]:,.2f}</td>'
            f'<td class="num">{_krw(p["value_krw"])}</td>'
            f'<td class="num">{p["weight"]:.0%}</td></tr>'
            for p in a["positions"])
        acc_body = (f'<p class="big">{_krw(a["equity_krw"])} <span class="unit">KRW</span></p>'
                    f'<p class="sub">현금 {_krw(a["cash_krw"])} ({a["cash_weight"]:.0%})</p>'
                    f'<table><thead><tr><th>종목</th><th>수량</th><th>현재가</th>'
                    f'<th>평가액</th><th>비중</th></tr></thead><tbody>{rows}</tbody></table>')

    # performance card
    if perf.get("strategy_return") is not None:
        bmk = "".join(f'<li>{esc(k)} <b>{v:+.2%}</b></li>'
                      for k, v in perf.get("benchmarks", {}).items())
        rc = "#16a34a" if perf["strategy_return"] >= 0 else "#dc2626"
        perf_body = (f'<p class="big" style="color:{rc}">{perf["strategy_return"]:+.2%}</p>'
                     f'<p class="sub">since {esc(perf["since"])} · 방어 베타(리스크관리)</p>'
                     f'<ul class="bmk">{bmk}</ul>')
    else:
        perf_body = '<p class="sub">아직 성과 데이터 수집 중</p>'

    # jobs card
    job_items = []
    for j in s["sections"]["jobs"]:
        color = "#16a34a" if j["ok"] else ("#9ca3af" if j["never"] else "#dc2626")
        age = "없음" if j["never"] else f"{j['age_hours']:.0f}h 전"
        job_items.append(
            f'<li><span class="dot" style="background:{color}"></span>'
            f'{esc(j["label"])}<span class="age">{esc(age)}</span></li>')
    jobs_body = f'<ul class="jobs">{"".join(job_items)}</ul>'

    # data card
    d = s["sections"]["data"]
    data_body = (f'<p class="err">{esc(str(d["error"]))}</p>' if d.get("error")
                 else f'<p class="big">{d["ok"]}/{d["symbols"]}</p>'
                      f'<p class="sub">최신 {esc(str(d["newest"]))}</p>')

    # fills card
    fills = s["sections"]["fills"]
    fills_body = ("".join(
        f'<li>{esc(f["when"])} · {esc(f["market"])} <b>{esc(f["side"])} {f["qty"]}</b> '
        f'{esc(f["etf"])}</li>' for f in reversed(fills)) or "<li>—</li>")

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>makemoney 상태</title>
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
 background:#0b0e14;color:#e6e6e6;padding:24px}}
header{{display:flex;align-items:center;gap:12px;margin:0 auto 20px;max-width:960px}}
header h1{{font-size:20px;margin:0;font-weight:600}}
.badge{{display:inline-flex;align-items:center;gap:8px;padding:4px 12px;border-radius:999px;
 background:#161b26;font-size:13px}}
.badge .dot{{width:10px;height:10px;border-radius:50%;background:{dot}}}
.ts{{margin-left:auto;color:#8b93a7;font-size:13px}}
.grid{{max-width:960px;margin:0 auto;display:grid;gap:16px;
 grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}}
.card{{background:#161b26;border:1px solid #232a3a;border-radius:14px;padding:18px 20px}}
.card h2{{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:#8b93a7;margin:0 0 10px}}
.big{{font-size:28px;font-weight:700;margin:4px 0}}
.unit{{font-size:14px;color:#8b93a7;font-weight:400}}
.sub{{color:#8b93a7;font-size:13px;margin:2px 0 8px}}
.err{{color:#f87171}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px}}
th,td{{text-align:left;padding:4px 6px;border-bottom:1px solid #232a3a}}
td.num,th:nth-child(n+2){{text-align:right}}
.mkt{{color:#8b93a7;font-size:11px}}
ul{{list-style:none;margin:6px 0 0;padding:0}}
.jobs li,.bmk li{{display:flex;align-items:center;gap:8px;padding:3px 0;font-size:14px}}
.jobs .dot{{width:9px;height:9px;border-radius:50%}}
.jobs .age{{margin-left:auto;color:#8b93a7;font-size:12px}}
.bmk li b{{margin-left:auto}}
.warn{{max-width:960px;margin:0 auto 16px;padding:10px 14px;border-radius:10px;
 background:#3b1213;border:1px solid #7f1d1d;color:#fca5a5;font-size:13px}}
footer{{max-width:960px;margin:18px auto 0;color:#5b6478;font-size:12px}}
</style></head><body>
<header><h1>makemoney</h1>
<span class="badge"><span class="dot"></span>{esc(label)}</span>
<span class="ts">{esc(s["as_of"][:16].replace("T", " "))} UTC · 5분마다 갱신</span></header>
{'<div class="warn">⚠️ ' + esc(" | ".join(s["problems"])) + "</div>" if s["problems"] else ""}
<div class="grid">
{card("자산", acc_body)}
{card("성과", perf_body)}
{card("작업 상태", jobs_body)}
{card("데이터", data_body)}
{card("최근 체결", f'<ul>{fills_body}</ul>')}
</div>
<footer>방어 베타(리스크관리) · 모의투자 · 실거래 아님. 알파 없음 — 시장을 낮은 낙폭으로 추종.</footer>
</body></html>"""


def write_html(s: dict, path: str = "status.html") -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_html(s))
    return path
