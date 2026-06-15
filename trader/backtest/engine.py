# trader/backtest/engine.py
from __future__ import annotations
from trader.data.interfaces import DataFeed
from trader.execution.interfaces import ExecutionHandler
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio

class BacktestEngine:
    """표준 이벤트 루프. live/engine.py와 동일한 순서를 따른다 (패리티의 근간)."""
    def __init__(self, feed: DataFeed, strategy: FusionEngine,
                 execution: ExecutionHandler, portfolio: Portfolio, audit=None):
        for src in strategy.sources:
            if getattr(src, "supports_backtest", True) is False:
                raise ValueError(
                    f"live-only signal source '{src.name}' cannot be used in backtest"
                )
        self.feed, self.strategy, self.execution, self.portfolio = feed, strategy, execution, portfolio
        self.audit = audit
    def run(self) -> None:
        for bar in self.feed.events():
            for fill in self.execution.on_bar(bar):     # 전일 주문을 이 봉 '시가'에 체결
                self.strategy.on_fill(fill)
                if self.audit: self.audit.record_fill(fill)
            self.portfolio.mark(bar)                      # 종가 마킹
            orders = self.strategy.on_bar(bar)            # 종가 판단
            for order in orders:
                self.execution.submit_order(order)        # 다음 봉 대기
                if self.audit: self.audit.record_order(order)
