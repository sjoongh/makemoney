# trader/strategy/beta_allocator.py
"""RESEARCH/PAPER — single-instrument beta allocator (pure decision logic).

Turns the risk-managed beta/defensive signal (EWMA vol-target + trend cash-switch)
into ONE concrete rebalance order for a market ETF (e.g. KODEX 200, 069500) on a
KRW account: hold `exposure × equity` worth of the ETF, the rest in cash.

Pure and side-effect-free — no KIS calls, no orders here. The paper executor
(separate) feeds it live inputs and submits the resulting delta through the
existing pre-trade gate + kill switch. Look-ahead-safe: exposure is computed
from index history up to the decision day only.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Optional

from trader.strategy.vol_target import PortfolioVolTargeter


def robust_index_returns(
    bars_by_symbol: dict,
    *,
    min_coverage: float = 0.5,
    exclude_from: Optional[_date] = None,
) -> list:
    """Equal-weight index daily returns with a COVERAGE FLOOR and partial-bar
    exclusion — the live-executor-safe replacement for raw ew_daily_returns.

    Guards (audit 2026-07-02): a ragged panel tail let the raw EW return be
    computed from 3/200 names (+4.88% garbage) and feed vol targeting; and the
    13:00 KST accumulator wrote PARTIAL intraday KOSPI bars for the fetch day.

      - a date contributes a return only if >= min_coverage of all names have
        prices on BOTH that date and the previous kept date;
      - dates >= exclude_from are dropped entirely (e.g. today's partial bar).

    Returns ascending [(date, ret)].
    """
    price: dict = {}
    all_dates: set = set()
    for sym, bars in bars_by_symbol.items():
        m = {b.ts.date(): b.close for b in bars}
        price[sym] = m
        all_dates.update(m)
    if exclude_from is not None:
        all_dates = {d for d in all_dates if d < exclude_from}
    dates = sorted(all_dates)
    n_names = len(price)
    out: list = []
    prev = None
    for d in dates:
        cov = sum(1 for m in price.values() if d in m)
        if n_names == 0 or cov / n_names < min_coverage:
            continue  # ragged/holiday date — skip entirely
        if prev is not None:
            rets = []
            for m in price.values():
                p0, p1 = m.get(prev), m.get(d)
                if p0 and p1 and p0 > 0:
                    rets.append(p1 / p0 - 1.0)
            if len(rets) >= n_names * min_coverage:
                out.append((d, sum(rets) / len(rets)))
        prev = d
    return out


def latest_exposure(
    index_returns: list[float],
    *,
    target_vol: float = 0.15,
    trend_window: Optional[int] = 200,
    max_leverage: float = 1.0,
) -> float:
    """Current target market exposure in [0, max_leverage] from the defensive
    beta signal, using the full index daily-return history (most recent last).

    exposure = vol_target_scalar × (1 if index_level > trailing-MA else 0)
    """
    if not index_returns:
        return 0.0
    targeter = PortfolioVolTargeter(target_vol=target_vol, max_scalar=max_leverage)
    level = 1.0
    levels = [1.0]
    targeter.update(level)
    for r in index_returns:
        level *= (1.0 + r)
        levels.append(level)
        targeter.update(level)

    vol_scalar = min(targeter.scalar(), max_leverage)
    in_market = True
    if trend_window is not None and len(levels) >= trend_window:
        sma = sum(levels[-trend_window:]) / trend_window
        in_market = levels[-1] > sma
    return vol_scalar * (1.0 if in_market else 0.0)


def rebalance_order(
    exposure: float,
    etf_price: float,
    cash_krw: float,
    current_shares: int,
    *,
    equity_krw: Optional[float] = None,
    min_trade_shares: int = 1,
    rebalance_band: float = 0.05,
) -> dict:
    """Compute the rebalance order toward `exposure × equity` in the ETF.

    ``equity_krw`` should be the TRUE, SHARED total account equity (settled
    cash + ALL positions across sleeves).  When multiple sleeves size against
    the same account, passing it explicitly is REQUIRED for correctness —
    deriving equity per-sleeve as cash + own-shares double-counts the shared
    cash across sleeves (this caused runaway over-buying; fixed 2026-07-02).
    Falls back to cash + own-position value only when not provided (single-
    sleeve/backtest use).

    Only trades when the share delta is at least `min_trade_shares` AND the
    weight gap exceeds `rebalance_band` (avoids churny tiny rebalances/costs).
    Buys are additionally capped by available ``cash_krw``. Returns a decision
    dict with side in {"BUY","SELL","HOLD"} and an unsigned quantity.
    """
    if etf_price <= 0:
        return {"side": "HOLD", "qty": 0, "reason": "bad price",
                "target_shares": current_shares, "exposure": exposure}

    equity = equity_krw if equity_krw is not None else cash_krw + current_shares * etf_price
    target_value = max(0.0, exposure) * equity
    target_shares = int(target_value // etf_price)

    # can't buy more than cash allows
    if target_shares > current_shares:
        affordable = current_shares + int(cash_krw // etf_price)
        target_shares = min(target_shares, affordable)

    delta = target_shares - current_shares
    cur_w = (current_shares * etf_price) / equity if equity > 0 else 0.0
    tgt_w = (target_shares * etf_price) / equity if equity > 0 else 0.0

    if abs(delta) < min_trade_shares or abs(tgt_w - cur_w) < rebalance_band:
        return {"side": "HOLD", "qty": 0, "reason": "within band",
                "target_shares": target_shares, "current_shares": current_shares,
                "exposure": exposure, "cur_weight": cur_w, "tgt_weight": tgt_w}

    side = "BUY" if delta > 0 else "SELL"
    return {"side": side, "qty": abs(delta), "reason": "rebalance",
            "target_shares": target_shares, "current_shares": current_shares,
            "exposure": exposure, "cur_weight": cur_w, "tgt_weight": tgt_w}
