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

from typing import Optional

from trader.strategy.vol_target import PortfolioVolTargeter


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
    min_trade_shares: int = 1,
    rebalance_band: float = 0.05,
) -> dict:
    """Compute the rebalance order toward `exposure × equity` in the ETF.

    equity = cash + current_shares × price. Only trades when the share delta is
    at least `min_trade_shares` AND the weight gap exceeds `rebalance_band`
    (avoids churny tiny rebalances / costs). Returns a decision dict with side
    in {"BUY","SELL","HOLD"} and an unsigned quantity.
    """
    if etf_price <= 0:
        return {"side": "HOLD", "qty": 0, "reason": "bad price",
                "target_shares": current_shares, "exposure": exposure}

    equity = cash_krw + current_shares * etf_price
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
