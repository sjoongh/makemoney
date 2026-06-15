# trader/app/run_paper.py
from __future__ import annotations
import httpx
from trader.app.config import AppConfig
from trader.execution.kis_client import KisClient
from trader.data.kis_live_feed import KisLiveFeed
from trader.execution.kis_paper import KisPaperExecutionHandler
from trader.strategy.fusion_engine import FusionEngine
from trader.strategy.portfolio import Portfolio, FxRates
from trader.strategy.risk import RiskManager
from trader.strategy.order_factory import OrderFactory
from trader.signals.technical import TechnicalSignalSource  # kept for parity tests
from trader.signals.technical_indicator_source import TechnicalIndicatorSource
from trader.signals.indicators import (
    MovingAverageCross,
    RsiReversion,
    MacdTrend,
    BollingerReversion,
)
from trader.live.engine import LiveEngine
from trader.data.recorder import BarRecorder

def main() -> None:
    cfg = AppConfig.from_env()
    kis = KisClient(httpx.Client(base_url="https://openapivts.koreainvestment.com:29443"),
                    cfg.kis_app_key, cfg.kis_app_secret, cfg.kis_account, paper=True)
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":10_000_000.0}, fx)
    # 순수 기술신호 시스템. 뉴스 소스(trader/signals/news/)는 레포에 보존돼 있고
    # 라이브 전용이라 인트라데이로 전환할 때 다시 연결 가능. 현재는 미연결.
    sources = [
        TechnicalIndicatorSource(name="technical.ma_10_30",  indicator=MovingAverageCross(10, 30)),
        TechnicalIndicatorSource(name="technical.rsi_14",    indicator=RsiReversion(14, 30, 70)),
        TechnicalIndicatorSource(name="technical.macd",      indicator=MacdTrend(12, 26, 9)),
        TechnicalIndicatorSource(name="technical.boll_20_2", indicator=BollingerReversion(20, 2.0)),
    ]
    eng = FusionEngine(
        sources,
        pf, RiskManager(0.3), OrderFactory(),
        source_weight={
            "technical.ma_10_30":  0.30,
            "technical.rsi_14":    0.20,
            "technical.macd":      0.30,
            "technical.boll_20_2": 0.20,
        },
    )
    feed = KisLiveFeed(kis, [("AAPL","NASDAQ","USD"), ("005930","KOSPI","KRW")])
    LiveEngine(feed, eng, KisPaperExecutionHandler(kis), pf, recorder=BarRecorder()).run()

if __name__ == "__main__":
    main()
