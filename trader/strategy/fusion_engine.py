# trader/strategy/fusion_engine.py
from __future__ import annotations
from typing import Sequence
from trader.core.events import BarEvent, OrderEvent, FillEvent, NormalizedSignal, TargetPosition
from trader.signals.interfaces import SignalSource

class FusionEngine:
    """모드 무지. 신호 융합 → 목표비중 → 리스크 → 주문. 브로커/DB/시계 직접 접근 없음."""
    def __init__(self, signal_sources: Sequence[SignalSource], portfolio,
                 risk_manager, order_factory, enter_threshold: float = 0.35,
                 exit_threshold: float | None = None,
                 source_weight: dict[str, float] | None = None,
                 vol_targeter=None):
        self.sources = signal_sources
        self.portfolio = portfolio
        self.risk = risk_manager
        self.order_factory = order_factory
        self.enter_threshold = enter_threshold
        self.exit_threshold = exit_threshold if exit_threshold is not None else -enter_threshold
        self.source_weight = source_weight or {}
        # vol_targeter: PortfolioVolTargeter | None.  None = identity (default-off, parity-safe).
        self.vol_targeter = vol_targeter
    def on_fill(self, fill: FillEvent) -> None:
        self.portfolio.apply_fill(fill)
    def _combine(self, signals: list[NormalizedSignal]) -> float:
        if not signals: return 0.0
        num = den = 0.0
        for s in signals:
            w = s.confidence * self.source_weight.get(s.source, 1.0)
            num += s.score * w; den += w
        return num / den if den else 0.0

    def combined_score(self, signals: list) -> float:
        """Public alias for _combine — returns the weighted combined score."""
        return self._combine(signals)

    def observe_bar(self, bar: BarEvent) -> list:
        """Update risk state and collect signals. Returns list[NormalizedSignal]."""
        self.risk.on_bar(bar, self.portfolio)  # two-phase: update ATR + daily loss state first
        return [s for src in self.sources if (s := src.on_bar(bar)) is not None]

    def decide_orders(self, bar: BarEvent, signals: list) -> list[OrderEvent]:
        """Given pre-collected signals, apply threshold logic and emit orders.

        Vol-targeting ordering (no look-ahead):
          1. scalar() is read FIRST — it reflects EWMA variance through yesterday.
          2. Orders are sized using that scalar.
          3. update() is called AFTER sizing with today's equity — today's return
             is stored for tomorrow's scalar, never for today's.
        When vol_targeter is None the path is byte-identical to the original.
        """
        combined = self._combine(signals)
        if combined >= self.enter_threshold:
            weight = combined
        elif combined <= self.exit_threshold:
            weight = 0.0
        else:
            # Neutral zone: no new order. Still update targeter so it tracks equity.
            if self.vol_targeter is not None:
                self.vol_targeter.update(self.portfolio.equity_krw())
            return []  # 중립 구간: 포지션 유지, 주문 없음
        target = TargetPosition(bar.symbol, weight, reason=f"combined={combined:.2f}")
        sized = self.risk.size_target(target, self.portfolio, bar)

        # ── Vol targeting (default-off: vol_targeter is None → identity) ──────
        if self.vol_targeter is not None:
            # Step 1: read scalar BEFORE update (reflects returns through yesterday)
            s = self.vol_targeter.scalar()
            scaled_weight = sized.target_weight * s
            sized = TargetPosition(sized.symbol, scaled_weight, reason=sized.reason)
            # Step 2: update with today's equity AFTER sizing (no same-day leak)
            self.vol_targeter.update(self.portfolio.equity_krw())

        return self.order_factory.orders_for_target(sized, self.portfolio, price=bar.close, ts=bar.ts)

    def warmup_bar(self, bar: BarEvent) -> None:
        """Update state only — never emits orders. For warming up indicators before live trading."""
        self.observe_bar(bar)

    def on_bar(self, bar: BarEvent) -> list[OrderEvent]:
        return self.decide_orders(bar, self.observe_bar(bar))
