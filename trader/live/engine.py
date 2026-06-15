# trader/live/engine.py
from __future__ import annotations
from trader.data.interfaces import DataFeed
from trader.execution.interfaces import ExecutionHandler
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio

class LiveEngine:
    """라이브 루프. BacktestEngine과 동일한 이벤트 처리 순서 — 이것이 패리티의 근간.
    실거래에서는 feed=KIS라이브, execution=KIS페이퍼로만 바뀐다."""
    def __init__(self, feed: DataFeed, strategy: FusionEngine,
                 execution: ExecutionHandler, portfolio: Portfolio,
                 audit=None, recorder=None):
        self.feed, self.strategy, self.execution, self.portfolio = feed, strategy, execution, portfolio
        self.audit, self.recorder = audit, recorder
    def run(self) -> None:
        for bar in self.feed.events():
            if self.recorder: self.recorder.record_bar(bar)
            for fill in self.execution.on_bar(bar):
                self.strategy.on_fill(fill)
                if self.audit: self.audit.record_fill(fill)
            self.portfolio.mark(bar)
            for order in self.strategy.on_bar(bar):
                self.execution.submit_order(order)
                if self.audit: self.audit.record_order(order)
