# trader/strategy/risk.py
from __future__ import annotations
from datetime import date
from trader.core.events import BarEvent, TargetPosition
from trader.strategy.portfolio import Portfolio


def _sym_key(sym) -> tuple[str, str]:
    return (sym.market.value, sym.ticker)


class RiskManager:
    def __init__(self, max_symbol_weight: float = 0.30, *,
                 atr_period: int = 14, target_atr_pct: float = 0.03,
                 daily_loss_limit_pct: float = 0.03,
                 max_market_weight: dict | None = None,
                 max_positions: int | None = None):
        self.max_symbol_weight = max_symbol_weight
        self.atr_period = atr_period
        self.target_atr_pct = target_atr_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.max_market_weight = max_market_weight or {}
        self.max_positions = max_positions

        # Permanent kill switch
        self._killed: bool = False

        # Daily loss tracking
        self._daily_killed: bool = False
        self._current_day: date | None = None
        self._day_start_equity_krw: float = 0.0

        # ATR state: per-symbol (market, ticker) key
        # _atr_bars[key] = list of true ranges collected
        # _atr[key] = current Wilder MA of TR (once warmed)
        # _prev_close[key] = previous bar's close (for TR calc)
        self._atr_bars: dict[tuple[str, str], list[float]] = {}
        self._atr: dict[tuple[str, str], float] = {}
        self._prev_close: dict[tuple[str, str], float] = {}

    def trip_kill_switch(self) -> None:
        self._killed = True

    def on_bar(self, bar: BarEvent, portfolio: Portfolio) -> None:
        """Update ATR state and check daily loss limit."""
        key = _sym_key(bar.symbol)

        # ── ATR update (Wilder MA of True Range) ──────────────────────────
        prev_close = self._prev_close.get(key)
        if prev_close is None:
            # First bar for this symbol: TR = high - low (no prev close)
            tr = bar.high - bar.low
        else:
            tr = max(bar.high - bar.low,
                     abs(bar.high - prev_close),
                     abs(bar.low - prev_close))
        self._prev_close[key] = bar.close

        if key not in self._atr:
            # Collecting bars for initial seed
            buf = self._atr_bars.setdefault(key, [])
            buf.append(tr)
            if len(buf) >= self.atr_period:
                # Seed: simple average of first atr_period TRs
                self._atr[key] = sum(buf) / len(buf)
                del self._atr_bars[key]
        else:
            # Wilder smoothing: ATR = (ATR*(n-1) + TR) / n
            n = self.atr_period
            self._atr[key] = (self._atr[key] * (n - 1) + tr) / n

        # ── Day rollover / daily loss check ───────────────────────────────
        bar_date = bar.ts.date()
        if self._current_day is None or bar_date != self._current_day:
            # New day: record equity at day start, reset daily kill
            self._current_day = bar_date
            self._day_start_equity_krw = portfolio.equity_krw()
            self._daily_killed = False
        else:
            # Same day: check for daily loss breach
            if self._day_start_equity_krw > 0:
                loss_pct = 1.0 - portfolio.equity_krw() / self._day_start_equity_krw
                if loss_pct > self.daily_loss_limit_pct:
                    self._daily_killed = True

    def size_target(self, target: TargetPosition,
                    portfolio: Portfolio, bar: BarEvent) -> TargetPosition:
        """Apply all risk gates and return a (possibly reduced) TargetPosition."""
        sym = target.symbol
        reason = target.reason

        # ── Zero or negative → flat ────────────────────────────────────────
        if target.target_weight <= 0.0:
            return TargetPosition(sym, 0.0, reason)

        # ── Kill switches ──────────────────────────────────────────────────
        if self._killed or self._daily_killed:
            kill_reason = (reason + "|risk=kill").lstrip("|")
            return TargetPosition(sym, 0.0, kill_reason)

        # ── Symbol weight cap ──────────────────────────────────────────────
        w = min(target.target_weight, self.max_symbol_weight)

        # ── Volatility scaling via ATR ─────────────────────────────────────
        key = _sym_key(sym)
        if key in self._atr and bar.close > 0:
            atr_pct = self._atr[key] / bar.close
            if atr_pct > 0:
                w *= min(1.0, self.target_atr_pct / atr_pct)

        # ── Market weight cap ──────────────────────────────────────────────
        market = sym.market
        cap = self.max_market_weight.get(market)
        if cap is not None:
            current_market_w = portfolio.market_weight(market)
            current_sym_w = portfolio.position_weight(sym)
            # Available room: cap minus (market weight excluding this symbol's existing)
            available = cap - (current_market_w - current_sym_w)
            w = min(w, max(0.0, available))

        # ── Max positions gate ─────────────────────────────────────────────
        if self.max_positions is not None:
            already_held = portfolio.position(sym) != 0
            if not already_held and portfolio.open_position_count() >= self.max_positions:
                w = 0.0

        return TargetPosition(sym, max(0.0, w), reason)
