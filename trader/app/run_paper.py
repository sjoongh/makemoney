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
from trader.signals.technical import TechnicalSignalSource
from trader.signals.news.source import NewsSignalSource
from trader.signals.news.providers import MockNewsProvider
from trader.signals.news.sentiment import MockSentimentScorer
from trader.live.engine import LiveEngine
from trader.data.recorder import BarRecorder

def main() -> None:
    cfg = AppConfig.from_env()
    kis = KisClient(httpx.Client(base_url="https://openapivts.koreainvestment.com:29443"),
                    cfg.kis_app_key, cfg.kis_app_secret, cfg.kis_account, paper=True)
    fx = FxRates({"USD":1300.0,"KRW":1.0})
    pf = Portfolio({"KRW":10_000_000.0}, fx)
    # MockNewsProvider([]) emits no items → news source returns None on every bar
    # and behaves identically to technical-only until real API keys are wired.
    news = NewsSignalSource(MockNewsProvider([]), MockSentimentScorer())
    eng = FusionEngine(
        [TechnicalSignalSource(20, 50), news],
        pf, RiskManager(0.3), OrderFactory(),
        source_weight={"technical": 1.0, "news_llm": 0.5},   # conservative news weight
    )
    feed = KisLiveFeed(kis, [("AAPL","NASDAQ","USD"), ("005930","KOSPI","KRW")])
    LiveEngine(feed, eng, KisPaperExecutionHandler(kis), pf, recorder=BarRecorder()).run()

if __name__ == "__main__":
    main()
