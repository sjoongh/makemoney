# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-15T08:45:17.322Z

## Original task

I'm integrating the Korea Investment & Securities (한국투자증권) KIS Open API for PAPER trading (모의투자, domain https://openapivts.koreainvestment.com:29443). Token issuance via POST /oauth2/tokenP already works.

Give me the EXACT REST details (path, HTTP method, tr_id for PAPER/모의투자, key query params or JSON body fields, and required headers) for these 5 calls. Paper trading tr_ids usually start with 'V'. Be precise; if unsure on a value say so explicitly rather than inventing.

1. Overseas (US NASDAQ) daily stock price inquiry (일별 시세) — to get historical daily OHLCV bars.
2. Domestic (KOSPI) daily stock price inquiry — daily OHLCV.
3. Overseas (US) stock order for PAPER trading (buy/sell) — tr_id for buy and sell.
4. Domestic stock order for PAPER trading (order-cash) — tr_id for buy and sell.
5. Order fill / execution inquiry (체결 조회) for paper — both domestic and overseas if different.

Also list the common required HTTP headers for KIS REST calls (authorization, appkey, appsecret, tr_id, custtype, and for overseas any exchange code param like EXCD/excg). Keep it as a compact reference table.

## Final prompt

I'm integrating the Korea Investment & Securities (한국투자증권) KIS Open API for PAPER trading (모의투자, domain https://openapivts.koreainvestment.com:29443). Token issuance via POST /oauth2/tokenP already works.

Give me the EXACT REST details (path, HTTP method, tr_id for PAPER/모의투자, key query params or JSON body fields, and required headers) for these 5 calls. Paper trading tr_ids usually start with 'V'. Be precise; if unsure on a value say so explicitly rather than inventing.

1. Overseas (US NASDAQ) daily stock price inquiry (일별 시세) — to get historical daily OHLCV bars.
2. Domestic (KOSPI) daily stock price inquiry — daily OHLCV.
3. Overseas (US) stock order for PAPER trading (buy/sell) — tr_id for buy and sell.
4. Domestic stock order for PAPER trading (order-cash) — tr_id for buy and sell.
5. Order fill / execution inquiry (체결 조회) for paper — both domestic and overseas if different.

Also list the common required HTTP headers for KIS REST calls (authorization, appkey, appsecret, tr_id, custtype, and for overseas any exchange code param like EXCD/excg). Keep it as a compact reference table.

## Raw output

```text
Verified against the official KIS `open-trading-api` samples and KIS API portal pages. Base URL for paper: `https://openapivts.koreainvestment.com:29443`.

| # | Call | Method + path | PAPER `tr_id` | Key params/body |
|---|---|---|---|---|
| 1 | Overseas US/NASDAQ daily OHLCV, `해외주식 기간별시세` | `GET /uapi/overseas-price/v1/quotations/dailyprice` | `HHDFS76240000` | Query: `AUTH=""`, `EXCD="NAS"` for NASDAQ price inquiry, `SYMB="AAPL"`, `GUBN="0"` daily, `BYMD="YYYYMMDD"` 기준일, `MODP="0"`/`"1"` 수정주가 여부. Note: quote TR is same for real/paper, not `V...`. |
| 2 | Domestic KOSPI/KRX historical daily OHLCV, `국내주식기간별시세(일/주/월/년)` | `GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | `FHKST03010100` | Query: `FID_COND_MRKT_DIV_CODE="J"` for KRX, `FID_INPUT_ISCD="005930"`, `FID_INPUT_DATE_1="YYYYMMDD"`, `FID_INPUT_DATE_2="YYYYMMDD"`, `FID_PERIOD_DIV_CODE="D"`, `FID_ORG_ADJ_PRC="0"` 수정주가 / `"1"` 원주가 per sample. Quote TR is same for paper. |
| 3 | Overseas US stock order, paper | `POST /uapi/overseas-stock/v1/trading/order` | Buy: `VTTT1002U`; Sell: `VTTT1006U` | JSON body: `CANO`, `ACNT_PRDT_CD`, `OVRS_EXCG_CD="NASD"` for NASDAQ orders, `PDNO="AAPL"`, `ORD_QTY`, `OVRS_ORD_UNPR` (`"0"` for market-style where accepted; paper US sample notes only `ORD_DVSN="00"` limit is supported), `ORD_DVSN="00"`, `ORD_SVR_DVSN_CD="0"`, `CTAC_TLNO=""`, `MGCO_APTM_ODNO=""`, `SLL_TYPE=""` for buy / `"00"` for sell. |
| 4 | Domestic stock cash order, paper | `POST /uapi/domestic-stock/v1/trading/order-cash` | Buy: `VTTC0012U`; Sell: `VTTC0011U` | JSON body: `CANO`, `ACNT_PRDT_CD`, `PDNO="005930"`, `ORD_DVSN`, `ORD_QTY`, `ORD_UNPR`, `EXCG_ID_DVSN_CD="KRX"`; optional `SLL_TYPE` for sell, `CNDT_PRIC`. |
| 5a | Overseas order/fill inquiry, paper, `해외주식 주문체결내역` | `GET /uapi/overseas-stock/v1/trading/inquire-ccnl` | `VTTS3035R` | Query: `CANO`, `ACNT_PRDT_CD`, `PDNO` (`""` for all in paper per sample), `ORD_STRT_DT`, `ORD_END_DT`, `SLL_BUY_DVSN="00"` paper all only, `CCLD_NCCS_DVSN="00"` paper all only, `OVRS_EXCG_CD=""` paper all only, `SORT_SQN="DS"`, `ORD_DT=""`, `ORD_GNO_BRNO=""`, `ODNO=""`, `CTX_AREA_NK200=""`, `CTX_AREA_FK200=""`. |
| 5b | Domestic order/fill inquiry, paper, `주식일별주문체결조회` | `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld` | Within 3 months: `VTTC0081R`; older than 3 months: `VTSC9215R` | Query: `CANO`, `ACNT_PRDT_CD`, `INQR_STRT_DT`, `INQR_END_DT`, `SLL_BUY_DVSN_CD="00"` all / `"01"` sell / `"02"` buy, `PDNO`, `CCLD_DVSN="00"` all / `"01"` filled / `"02"` unfilled, `INQR_DVSN="00"` reverse / `"01"` normal, `INQR_DVSN_3="00"`, `EXCG_ID_DVSN_CD="KRX"` or `ALL`, `CTX_AREA_FK100=""`, `CTX_AREA_NK100=""`. |

Common REST headers:

```http
Content-Type: application/json
Accept: text/plain
charset: UTF-8
authorization: Bearer {access_token}
appkey: {paper_app_key}
appsecret: {paper_app_secret}
tr_id: {TR_ID}
custtype: P
tr_cont: ""        # or "N" for next-page continuation
```

For POST order calls, body keys must be uppercase. KIS samples state `hashkey` via `POST /uapi/hashkey` is currently optional, not mandatory; use it if you want tamper-checking on order bodies.

Sources: official KIS sample repo pages for [overseas stock functions](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/overseas_stock/overseas_stock_functions.py), [domestic stock functions](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/domestic_stock/domestic_stock_functions.py), and [auth/header handling](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/kis_auth.py); KIS API portal page for domestic daily price shown in search result.


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019eca71-517a-7781-b605-2d5d5c1f454a
--------
user
I'm integrating the Korea Investment & Securities (한국투자증권) KIS Open API for PAPER trading (모의투자, domain https://openapivts.koreainvestment.com:29443). Token issuance via POST /oauth2/tokenP already works.

Give me the EXACT REST details (path, HTTP method, tr_id for PAPER/모의투자, key query params or JSON body fields, and required headers) for these 5 calls. Paper trading tr_ids usually start with 'V'. Be precise; if unsure on a value say so explicitly rather than inventing.

1. Overseas (US NASDAQ) daily stock price inquiry (일별 시세) — to get historical daily OHLCV bars.
2. Domestic (KOSPI) daily stock price inquiry — daily OHLCV.
3. Overseas (US) stock order for PAPER trading (buy/sell) — tr_id for buy and sell.
4. Domestic stock order for PAPER trading (order-cash) — tr_id for buy and sell.
5. Order fill / execution inquiry (체결 조회) for paper — both domestic and overseas if different.

Also list the common required HTTP headers for KIS REST calls (authorization, appkey, appsecret, tr_id, custtype, and for overseas any exchange code param like EXCD/excg). Keep it as a compact reference table.
codex
I’ll verify this against current KIS documentation rather than relying on memory, because the paper `tr_id` values and endpoint names are easy to mix up.
web search: 
web search: KIS Open API 모의투자 해외주식 일별 시세 tr_id V daily price
codex
I found the official API portal pages and the official `koreainvestment/open-trading-api` sample repo. I’m going to use the repo samples to cross-check the portal pages, since they expose the exact endpoint strings and `tr_id` constants in code.
exec
/bin/zsh -lc 'pwd && rg --files . | head -50' in /Users/manager/side/makemoney
 succeeded in 0ms:
/Users/manager/side/makemoney
./docs/superpowers/specs/2026-06-15-phase1-trading-engine-design.md
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md
./tests/test_technical_indicators.py
./tests/test_fx_portfolio.py
./tests/test_kis_live_feed.py
./tests/test_no_lookahead.py
./tests/test_clock.py
./tests/test_interfaces.py
./tests/test_technical_signal.py
./tests/test_events.py
./tests/test_backtest_engine.py
./tests/test_backtest_live_parity.py
./tests/test_audit.py
./tests/test_kis_client.py
./tests/test_risk.py
./tests/test_kis_paper.py
./tests/test_execution_sim.py
./tests/__init__.py
./tests/test_historical_feed.py
./tests/test_metrics.py
./tests/test_fusion_engine.py
./tests/test_costs.py
./tests/test_replay_parity.py
./tests/test_order_factory.py
./pyproject.toml
./trader/strategy/portfolio.py
./trader/strategy/risk.py
./trader/strategy/__init__.py
./trader/strategy/order_factory.py
./trader/strategy/fusion_engine.py
./trader/data/historical_feed.py
./trader/data/kis_live_feed.py
./trader/data/storage.py
./trader/data/calendar.py
./trader/data/__init__.py
./trader/data/recorder.py
./trader/data/interfaces.py
./trader/live/engine.py
./trader/live/__init__.py
./trader/execution/kis_paper.py
./trader/execution/costs.py
./trader/execution/__init__.py
./trader/execution/kis_client.py
./trader/execution/simulated.py
./trader/execution/interfaces.py
./trader/backtest/report.py
./trader/backtest/engine.py
./trader/backtest/__init__.py
./trader/backtest/metrics.py
./trader/observability/__init__.py

exec
/bin/zsh -lc 'rg "tr_id|inquire-daily|order" trader tests -n' in /Users/manager/side/makemoney
 succeeded in 0ms:
tests/test_backtest_engine.py:10:from trader.strategy.order_factory import OrderFactory
trader/strategy/order_factory.py:1:# trader/strategy/order_factory.py
trader/strategy/order_factory.py:11:    def orders_for_target(self, target: TargetPosition, portfolio: Portfolio,
tests/test_kis_paper.py:12:    def submit_order(self, ticker, market, side, quantity):
tests/test_kis_paper.py:14:    def filled_orders(self):
tests/test_kis_paper.py:17:            return [{"order_id":"OID1","ticker":"AAPL","market":"NASDAQ","currency":"USD",
tests/test_kis_paper.py:21:def test_repeated_filled_orders_apply_only_once():
tests/test_kis_paper.py:29:        def submit_order(self, ticker, market, side, quantity): return "OID1"
tests/test_kis_paper.py:30:        def filled_orders(self):
tests/test_kis_paper.py:31:            return [{"order_id":"OID1","ticker":"AAPL","market":"NASDAQ","currency":"USD",
tests/test_kis_paper.py:34:    ex.submit_order(OrderEvent(uuid4(), sym, t(2), Side.BUY, 5))
tests/test_kis_paper.py:42:    ex.submit_order(OrderEvent(uuid4(), SYM, _t(2), Side.BUY, 5))
trader/execution/kis_paper.py:7:    """KIS 모의투자 실행. submit_order=KIS 제출, on_bar=확인된 체결만 FillEvent로 대사.
trader/execution/kis_paper.py:9:    동일 체결 중복 적용 방지: 브로커 order_id를 seen set으로 관리."""
trader/execution/kis_paper.py:12:        self._broker_to_order_id: dict[str, UUID] = {}   # broker_id -> original order UUID
trader/execution/kis_paper.py:15:    def submit_order(self, order: OrderEvent) -> None:
trader/execution/kis_paper.py:16:        broker_id = self._kis.submit_order(order.symbol.ticker, order.symbol.market.value,
trader/execution/kis_paper.py:17:                                           order.side.value, order.quantity)
trader/execution/kis_paper.py:19:            self._broker_to_order_id[broker_id] = order.order_id
trader/execution/kis_paper.py:23:        for f in self._kis.filled_orders():
trader/execution/kis_paper.py:24:            broker_fill_id = f["order_id"]
trader/execution/kis_paper.py:28:            order_id = self._broker_to_order_id.get(broker_fill_id, uuid4())
trader/execution/kis_paper.py:30:            out.append(FillEvent(order_id, sym, bar.ts, Side(f["side"]), int(f["qty"]),
tests/test_fusion_engine.py:7:from trader.strategy.order_factory import OrderFactory
tests/test_fusion_engine.py:22:def test_uptrend_produces_buy_order():
tests/test_fusion_engine.py:23:    eng = _engine(); orders = []
tests/test_fusion_engine.py:24:    for b in _bars([1,2,3,4,5,6]): orders = eng.on_bar(b) or orders
tests/test_fusion_engine.py:25:    assert any(o.side == Side.BUY for o in orders)
tests/test_fusion_engine.py:27:def test_same_inputs_same_orders_determinism():
tests/test_fusion_engine.py:34:def test_neutral_signal_holds_emits_no_orders():
tests/test_fusion_engine.py:40:    from trader.strategy.order_factory import OrderFactory
tests/test_fusion_engine.py:58:    orders = eng.on_bar(BarEvent(sym, datetime(2026,1,2,tzinfo=timezone.utc),10,10,10,10,100))
tests/test_fusion_engine.py:59:    assert orders == []   # 중립 → 무주문(홀드, 청산 금지)
trader/backtest/engine.py:20:            orders = self.strategy.on_bar(bar)            # 종가 판단
trader/backtest/engine.py:21:            for order in orders:
trader/backtest/engine.py:22:                self.execution.submit_order(order)        # 다음 봉 대기
trader/backtest/engine.py:23:                if self.audit: self.audit.record_order(order)
tests/test_clock.py:11:def test_trading_days_are_ordered_and_weekday_only():
trader/live/engine.py:13:                 audit=None, recorder=None):
trader/live/engine.py:15:        self.audit, self.recorder = audit, recorder
trader/live/engine.py:18:            if self.recorder: self.recorder.record_bar(bar)
trader/live/engine.py:23:            for order in self.strategy.on_bar(bar):
trader/live/engine.py:24:                self.execution.submit_order(order)
trader/live/engine.py:25:                if self.audit: self.audit.record_order(order)
trader/strategy/fusion_engine.py:10:                 risk_manager, order_factory, enter_threshold: float = 0.35,
trader/strategy/fusion_engine.py:16:        self.order_factory = order_factory
trader/strategy/fusion_engine.py:39:        return self.order_factory.orders_for_target(sized, self.portfolio, price=bar.close, ts=bar.ts)
tests/test_backtest_live_parity.py:10:from trader.strategy.order_factory import OrderFactory
tests/test_backtest_live_parity.py:22:        super().__init__(*a, **k); self.orders=[]
tests/test_backtest_live_parity.py:23:    def submit_order(self, order):
tests/test_backtest_live_parity.py:24:        self.orders.append((order.side, order.quantity)); super().submit_order(order)
tests/test_backtest_live_parity.py:33:def test_backtest_and_live_produce_identical_orders_and_equity():
tests/test_backtest_live_parity.py:37:    assert x1.orders == x2.orders                       # 동일 주문 시퀀스
tests/test_execution_sim.py:13:def test_order_fills_at_next_bar_open_not_same_bar():
tests/test_execution_sim.py:17:    ex.submit_order(OrderEvent(uuid4(), SYM, b1.ts, Side.BUY, 5))  # b1 종가 후 주문
tests/test_execution_sim.py:23:def test_order_for_unreprinted_symbol_never_fills():
tests/test_execution_sim.py:26:    ex.submit_order(OrderEvent(uuid4(), SYM, bar(2, 10.0).ts, Side.BUY, 5))
tests/test_replay_parity.py:4:from trader.data.recorder import BarRecorder
tests/test_replay_parity.py:13:    rec = BarRecorder()
trader/data/recorder.py:1:# trader/data/recorder.py
trader/data/recorder.py:5:class BarRecorder:
tests/test_order_factory.py:1:# tests/test_order_factory.py
tests/test_order_factory.py:5:from trader.strategy.order_factory import OrderFactory
tests/test_order_factory.py:15:    orders = of.orders_for_target(TargetPosition(SYM, 0.5), p, price=100.0, ts=_t())
tests/test_order_factory.py:16:    assert len(orders) == 1 and orders[0].side == Side.BUY and orders[0].quantity == 50
tests/test_order_factory.py:18:def test_no_order_when_delta_zero():
tests/test_order_factory.py:22:    assert of.orders_for_target(TargetPosition(SYM, 0.0), p, price=100.0, ts=_t()) == []
tests/test_audit.py:10:def test_audit_records_orders_and_fills_in_order():
tests/test_audit.py:12:    a.record_order(OrderEvent(uuid4(), SYM, _t(), Side.BUY, 5))
tests/test_audit.py:15:    assert kinds == ["order", "fill"]
tests/test_interfaces.py:16:    def submit_order(self, order): self.queued.append(order)
tests/test_interfaces.py:24:    ex.submit_order(OrderEvent(uuid4(), SYM, bar.ts, Side.BUY, 1))
tests/test_historical_feed.py:10:def test_feed_yields_in_timestamp_order_across_symbols():
trader/execution/kis_client.py:26:    def submit_order(self, ticker: str, market: str, side: str, quantity: int) -> str:
trader/execution/kis_client.py:27:        path = "/overseas/order" if market == "NASDAQ" else "/domestic/order"  # 실제 KIS 경로로 교체
trader/execution/kis_client.py:30:        return r.json().get("order_id", "")
trader/execution/kis_client.py:32:    def filled_orders(self) -> list[dict]:
trader/execution/kis_client.py:33:        r = self._c.get("/orders/filled"); r.raise_for_status()
trader/execution/interfaces.py:7:    def submit_order(self, order: OrderEvent) -> None:
trader/execution/simulated.py:15:    def submit_order(self, order: OrderEvent) -> None:
trader/execution/simulated.py:16:        self._pending.append(order)
trader/execution/simulated.py:23:                fills.append(FillEvent(o.order_id, o.symbol, bar.ts, o.side,
trader/app/run_backtest.py:10:from trader.strategy.order_factory import OrderFactory
trader/app/run_backtest.py:27:                for o in self.strategy.on_bar(bar): self.execution.submit_order(o)
trader/core/events.py:42:    order_id: UUID; symbol: Symbol; ts: datetime
trader/core/events.py:43:    side: Side; quantity: int; order_type: str = "MARKET"
trader/core/events.py:51:    order_id: UUID; symbol: Symbol; ts: datetime
trader/observability/audit.py:13:    def record_order(self, o: OrderEvent) -> None: self.records.append(_row("order", o))
trader/app/run_paper.py:11:from trader.strategy.order_factory import OrderFactory
trader/app/run_paper.py:14:from trader.data.recorder import BarRecorder
trader/app/run_paper.py:24:    LiveEngine(feed, eng, KisPaperExecutionHandler(kis), pf, recorder=BarRecorder()).run()

exec
/bin/zsh -lc 'git ls-remote https://github.com/koreainvestment/open-trading-api.git HEAD' in /Users/manager/side/makemoney
 succeeded in 2174ms:
33e0e1e65cd1c8c8b639531483ec0b327087bab1	HEAD

codex
The local client still has placeholder paths, so I’m not using it as a source of truth. I’m checking the official samples at the current repo HEAD (`33e0e1e...`) and will distinguish confirmed values from any ambiguous ones.
exec
/bin/zsh -lc 'tmp=$(mktemp -d) && git clone --depth 1 https://github.com/koreainvestment/open-trading-api.git "$tmp/open-trading-api" >/dev/null 2>&1 && printf '"'%s\\n' \""'$tmp/open-trading-api"' in /Users/manager/side/makemoney
 succeeded in 4278ms:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api

exec
/bin/zsh -lc "find . -maxdepth 3 -type f | sed 's#"'^./##'"' | rg \"overseas|domestic|daily|order|ccnl|period|price|inquire\" | head -200" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
strategy_builder/core/order_executor.py
legacy/rest/get_ovsstk_chart_price.py
legacy/rest/get_interest_stocks_price.py
legacy/rest/current_price_samle.py
legacy/rest/get_ovsfut_chart_price.py
stocks_info/domestic_index_future_code.py
stocks_info/domestic_commodity_future_code.py
stocks_info/domestic_elw_code.py
stocks_info/domestic_cme_future_code.py
stocks_info/domestic_bond_code.py
stocks_info/overseas_future_code.py
stocks_info/domestic_eurex_option_code.py
stocks_info/overseas_index_code.py
stocks_info/domestic_stock_future_code.py
stocks_info/overseas_stock_code.py
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py
examples_user/domestic_futureoption/domestic_futureoption_functions.py
examples_user/domestic_futureoption/domestic_futureoption_examples.py
examples_user/domestic_bond/domestic_bond_examples_ws.py
examples_user/domestic_bond/domestic_bond_functions_ws.py
examples_user/domestic_bond/domestic_bond_functions.py
examples_user/domestic_bond/domestic_bond_examples.py
examples_user/overseas_stock/overseas_stock_functions_ws.py
examples_user/overseas_stock/overseas_stock_functions.py
examples_user/overseas_stock/overseas_stock_examples.py
examples_user/overseas_stock/overseas_stock_examples_ws.py
examples_user/domestic_stock/domestic_stock_examples_ws.py
examples_user/domestic_stock/domestic_stock_examples.py
examples_user/domestic_stock/domestic_stock_functions.py
examples_user/domestic_stock/domestic_stock_functions_ws.py
examples_user/overseas_futureoption/overseas_futureoption_examples_ws.py
examples_user/overseas_futureoption/overseas_futureoption_examples.py
examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py
examples_user/overseas_futureoption/overseas_futureoption_functions.py

exec
/bin/zsh -lc 'rg "inquire-daily|daily-price|period-price|VTTT|VTTC|TTTC|JTTT|TTTS|order-rvsecncl|order-cash|inquire-.*ccnl|CCNL|체결|일별" -n rest examples_llm examples_user | head -300' in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
rg: rest: No such file or directory (os error 2)
examples_llm/etfetn/nav_comparison_time_trend/chk_nav_comparison_time_trend.py:35:    'cntg_vol': '체결 거래량'
examples_user/etfetn/etfetn_functions.py:149:    한국투자 HTS(eFriend Plus) > [0244] ETF/ETN 비교추이(NAV/IIV) 좌측 화면 "일별" 비교추이 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다.
examples_user/overseas_futureoption/overseas_futureoption_examples_ws.py:29:# [해외선물옵션]실시간시세 > 해외선물옵션 실시간체결가[실시간-017]
examples_user/overseas_futureoption/overseas_futureoption_examples_ws.py:35:# [해외선물옵션]실시간시세 > 해외선물옵션 실시간체결내역통보[실시간-020]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:19:# [해외선물옵션] 기본시세 > 해외선물 체결추이(일간) [해외선물-018]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:42:# [해외선물옵션] 주문/계좌 > 해외선물옵션 일별체결내역[해외선물-011]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:50:# [해외선물옵션] 주문/계좌 > 해외선물옵션 일별 주문내역 [해외선물-013]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:64:# [해외선물옵션] 주문/계좌 > 해외선물옵션 기간계좌손익 일별 [해외선물-010]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:139:# [해외선물옵션] 기본시세 > 해외선물 체결추이(월간)[해외선물-020]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:155:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(일간) [해외선물-037]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:170:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(월간) [해외선물-039]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:185:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(틱) [해외선물-038]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:193:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(주간) [해외선물-036]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:236:# [해외선물옵션] 기본시세 > 해외선물 체결추이(틱)[해외선물-019]
examples_user/overseas_futureoption/overseas_futureoption_examples.py:244:# [해외선물옵션] 기본시세 > 해외선물 체결추이(주간)[해외선물-017]
examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:99:# [해외선물옵션]실시간시세 > 해외선물옵션 실시간체결가[실시간-017]
examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:172:# [해외선물옵션]실시간시세 > 해외선물옵션 실시간체결내역통보[실시간-020]
examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:180:    해외선물옵션 실시간체결내역통보 API입니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:16:# [해외선물옵션] 기본시세 > 해외선물 체결추이(일간) [해외선물-018]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:36:    해외선물 체결추이(일간)[해외선물-018]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:37:    해외선물 체결추이(일간) API를 호출하여 DataFrame으로 반환합니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:55:        Tuple[pd.DataFrame, pd.DataFrame]: 해외선물 체결추이(일간) 데이터
examples_user/overseas_futureoption/overseas_futureoption_functions.py:307:    ccld_nccs_dvsn: str,  # 체결미체결구분
examples_user/overseas_futureoption/overseas_futureoption_functions.py:325:        ccld_nccs_dvsn (str): 01:전체 / 02:체결 / 03:미체결
examples_user/overseas_futureoption/overseas_futureoption_functions.py:429:# [해외선물옵션] 주문/계좌 > 해외선물옵션 일별체결내역[해외선물-011]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:452:    해외선물옵션 일별 체결내역[해외선물-011]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:453:    해외선물옵션 일별 체결내역 API를 호출하여 DataFrame으로 반환합니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:474:        Tuple[pd.DataFrame, pd.DataFrame]: 해외선물옵션 일별 체결내역 데이터
examples_user/overseas_futureoption/overseas_futureoption_functions.py:527:    api_url = "/uapi/overseas-futureoption/v1/trading/inquire-daily-ccld"
examples_user/overseas_futureoption/overseas_futureoption_functions.py:618:# [해외선물옵션] 주문/계좌 > 해외선물옵션 일별 주문내역 [해외선물-013]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:627:    ccld_nccs_dvsn: str,  # 체결미체결구분
examples_user/overseas_futureoption/overseas_futureoption_functions.py:639:    해외선물옵션 일별 주문내역[해외선물-013]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:640:    해외선물옵션 일별 주문내역 API를 호출하여 DataFrame으로 반환합니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:648:        ccld_nccs_dvsn (str): 체결미체결구분 (01:전체 / 02:체결 / 03:미체결)
examples_user/overseas_futureoption/overseas_futureoption_functions.py:659:        Optional[pd.DataFrame]: 해외선물옵션 일별 주문내역 데이터
examples_user/overseas_futureoption/overseas_futureoption_functions.py:707:    api_url = "/uapi/overseas-futureoption/v1/trading/inquire-daily-order"
examples_user/overseas_futureoption/overseas_futureoption_functions.py:877:# [해외선물옵션] 주문/계좌 > 해외선물옵션 기간계좌손익 일별 [해외선물-010]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:898:    해외선물옵션 기간계좌손익 일별[해외선물-010]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:899:    해외선물옵션 기간계좌손익 일별 API를 호출하여 DataFrame으로 반환합니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:918:        Tuple[pd.DataFrame, pd.DataFrame]: 해외선물옵션 기간계좌손익 일별 데이터
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2178:# [해외선물옵션] 기본시세 > 해외선물 체결추이(월간)[해외선물-020]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2198:    해외선물 체결추이(월간)[해외선물-020]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2199:    해외선물 체결추이(월간) API를 호출하여 DataFrame으로 반환합니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2217:        Tuple[pd.DataFrame, pd.DataFrame]: 해외선물 체결추이(월간) 데이터
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2461:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(일간) [해외선물-037]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2480:    해외옵션 체결추이(일간) API입니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2648:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(월간) [해외선물-039]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2667:    해외옵션 체결추이(월간) API입니다. 
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2701:        Tuple[pd.DataFrame, pd.DataFrame]: 해외옵션 체결추이(월간) 정보 (output1, output2)
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2726:    tr_id = "HHDFO55020300"  # 해외옵션 체결추이(월간)
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2837:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(틱) [해외선물-038]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2856:    해외옵션 체결추이(틱) API입니다. 
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2976:# [해외선물옵션] 기본시세 > 해외옵션 체결추이(주간) [해외선물-036]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:2995:    해외옵션 체결추이(주간) API입니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3056:    tr_id = "HHDFO55020000"  # 해외옵션 체결추이(주간)
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3118:    fm_lqd_ustl_ccld_dt: str,  # FM청산미결제체결일자
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3119:    fm_lqd_ustl_ccno: str,  # FM청산미결제체결번호
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3126:    ccld_cndt_cd: str,  # 체결조건코드
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3329:    api_url = "/uapi/overseas-futureoption/v1/trading/order-rvsecncl"
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3735:# [해외선물옵션] 기본시세 > 해외선물 체결추이(틱)[해외선물-019]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3755:    해외선물 체결추이(틱)[해외선물-019]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3756:    해외선물 체결추이(틱) API를 호출하여 DataFrame으로 반환합니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3774:        Tuple[pd.DataFrame, pd.DataFrame]: 해외선물 체결추이(틱) 데이터
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3898:# [해외선물옵션] 기본시세 > 해외선물 체결추이(주간)[해외선물-017]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3918:    해외선물 체결추이(주간)[해외선물-017]
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3919:    해외선물 체결추이(주간) API를 호출하여 DataFrame으로 반환합니다.
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3937:        Tuple[pd.DataFrame, pd.DataFrame]: 해외선물 체결추이(주간) 데이터
examples_user/domestic_bond/domestic_bond_examples_ws.py:29:# [장내채권] 실시간시세 > 일반채권 실시간체결가 [실시간-052]
examples_user/domestic_bond/domestic_bond_examples_ws.py:35:# [장내채권] 실시간시세 > 채권지수 실시간체결가 [실시간-060]
examples_user/domestic_bond/domestic_bond_examples.py:61:# [장내채권] 기본시세 > 장내채권현재가(체결) [국내주식-201]
examples_user/domestic_bond/domestic_bond_examples.py:68:# [장내채권] 주문/계좌 > 장내채권 일별체결조회 [국내주식-127]
examples_user/domestic_bond/domestic_bond_examples.py:83:# [장내채권] 기본시세 > 장내채권현재가(일별) [국내주식-202]
examples_llm/etfetn/nav_comparison_daily_trend/chk_nav_comparison_daily_trend.py:29:    'cntg_vol': '체결 거래량',
examples_user/domestic_bond/domestic_bond_functions_ws.py:96:# [장내채권] 실시간시세 > 일반채권 실시간체결가 [실시간-052]
examples_user/domestic_bond/domestic_bond_functions_ws.py:104:    일반채권 실시간체결가[H0BJCNT0] 구독 함수
examples_user/domestic_bond/domestic_bond_functions_ws.py:105:    한국투자증권 웹소켓 API를 통해 일반채권의 실시간 체결가 데이터를 구독합니다.
examples_user/domestic_bond/domestic_bond_functions_ws.py:143:        "stck_cntg_hour",  # 주식체결시간
examples_user/domestic_bond/domestic_bond_functions_ws.py:148:        "cntg_vol",  # 체결거래량
examples_user/domestic_bond/domestic_bond_functions_ws.py:159:        "cntg_type_cls_code",  # 체결유형코드
examples_user/domestic_bond/domestic_bond_functions_ws.py:165:# [장내채권] 실시간시세 > 채권지수 실시간체결가 [실시간-060]
examples_user/domestic_bond/domestic_bond_functions_ws.py:173:    채권지수 실시간체결가[H0BICNT0]
examples_user/domestic_bond/domestic_bond_functions_ws.py:174:    채권지수 실시간체결가 API를 통해 실시간 데이터를 구독합니다.
examples_user/domestic_futureoption/domestic_futureoption_examples.py:59:# [국내선물옵션] 기본시세 > 선물옵션 일중예상체결추이[국내선물-018]
examples_user/domestic_futureoption/domestic_futureoption_examples.py:101:# [국내선물옵션] 주문/계좌 > 선물옵션 주문체결내역조회[v1_국내선물-003]
examples_user/domestic_futureoption/domestic_futureoption_examples.py:118:# [국내선물옵션] 주문/계좌 > 선물옵션 기준일체결내역[v1_국내선물-016]
examples_user/domestic_futureoption/domestic_futureoption_examples.py:132:# [국내선물옵션] 주문/계좌 > 선물옵션기간약정수수료일별[v1_국내선물-017]
examples_user/domestic_futureoption/domestic_futureoption_examples.py:180:# [국내선물옵션] 주문/계좌 > (야간)선물옵션 주문체결 내역조회 [국내선물-009]
examples_llm/elw/indicator_trend_daily/indicator_trend_daily.py:22:# [국내주식] ELW시세 - ELW 투자지표추이(일별)[국내주식-173]
examples_llm/elw/indicator_trend_daily/indicator_trend_daily.py:38:    ELW 투자지표추이(일별)[국내주식-173]
examples_llm/elw/indicator_trend_daily/indicator_trend_daily.py:39:    ELW 투자지표추이(일별) API를 호출하여 DataFrame으로 반환합니다.
examples_llm/elw/indicator_trend_daily/indicator_trend_daily.py:50:        Optional[pd.DataFrame]: ELW 투자지표추이(일별) 데이터
examples_llm/etfetn/nav_comparison_daily_trend/nav_comparison_daily_trend.py:32:    한국투자 HTS(eFriend Plus) > [0244] ETF/ETN 비교추이(NAV/IIV) 좌측 화면 "일별" 비교추이 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다.
examples_user/domestic_bond/domestic_bond_functions.py:217:    tr_id = "TTTC0952U"
examples_user/domestic_bond/domestic_bond_functions.py:487:# [장내채권] 기본시세 > 장내채권현재가(체결) [국내주식-201]
examples_user/domestic_bond/domestic_bond_functions.py:500:    장내채권현재가(체결)[국내주식-201]
examples_user/domestic_bond/domestic_bond_functions.py:501:    장내채권현재가(체결) API를 호출하여 DataFrame으로 반환합니다.
examples_user/domestic_bond/domestic_bond_functions.py:512:        Optional[pd.DataFrame]: 장내채권현재가(체결) 데이터
examples_user/domestic_bond/domestic_bond_functions.py:536:    api_url = "/uapi/domestic-bond/v1/quotations/inquire-ccnl"
examples_user/domestic_bond/domestic_bond_functions.py:583:# [장내채권] 주문/계좌 > 장내채권 일별체결조회 [국내주식-127]
examples_user/domestic_bond/domestic_bond_functions.py:594:        nccs_yn: str,  # 미체결여부
examples_user/domestic_bond/domestic_bond_functions.py:605:    장내채권 주문체결내역[국내주식-127]
examples_user/domestic_bond/domestic_bond_functions.py:606:    장내채권 주문체결내역 API를 호출하여 DataFrame으로 반환합니다.
examples_user/domestic_bond/domestic_bond_functions.py:616:        nccs_yn (str): 미체결여부 (N(전체), C(체결), Y(미체결))
examples_user/domestic_bond/domestic_bond_functions.py:626:        Tuple[pd.DataFrame, pd.DataFrame]: 장내채권 주문체결내역 데이터
examples_user/domestic_bond/domestic_bond_functions.py:675:    api_url = "/uapi/domestic-bond/v1/trading/inquire-daily-ccld"
examples_user/domestic_bond/domestic_bond_functions.py:814:    api_url = "/uapi/domestic-bond/v1/quotations/inquire-daily-itemchartprice"
examples_user/domestic_bond/domestic_bond_functions.py:861:# [장내채권] 기본시세 > 장내채권 일별시세 [국내주식-202]
examples_user/domestic_bond/domestic_bond_functions.py:874:    장내채권현재가(일별)[국내주식-202]
examples_user/domestic_bond/domestic_bond_functions.py:875:    장내채권현재가(일별) API를 호출하여 DataFrame으로 반환합니다.
examples_user/domestic_bond/domestic_bond_functions.py:886:        Optional[pd.DataFrame]: 장내채권현재가(일별) 데이터
examples_user/domestic_bond/domestic_bond_functions.py:912:    api_url = "/uapi/domestic-bond/v1/quotations/inquire-daily-price"
examples_user/domestic_bond/domestic_bond_functions.py:1113:    tr_id = "TTTC8910R"
examples_user/domestic_bond/domestic_bond_functions.py:1437:    tr_id = "TTTC0953U"
examples_user/domestic_bond/domestic_bond_functions.py:1440:    api_url = "/uapi/domestic-bond/v1/trading/order-rvsecncl"
examples_user/domestic_bond/domestic_bond_functions.py:1638:    tr_id = "TTTC0958U"
examples_user/domestic_stock/domestic_stock_functions_ws.py:314:# [국내주식] 실시간시세 > 국내주식 실시간체결가(KRX) [실시간-003]
examples_user/domestic_stock/domestic_stock_functions_ws.py:323:    국내주식 실시간체결가 (KRX)[H0STCNT0] 구독 함수
examples_user/domestic_stock/domestic_stock_functions_ws.py:325:    이 함수는 한국투자증권 웹소켓 API를 통해 국내 주식의 실시간 체결가 데이터를 구독합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:386:# [국내주식] 실시간시세 > 국내주식 주식체결통보 [실시간-005]
examples_user/domestic_stock/domestic_stock_functions_ws.py:395:    국내주식 실시간체결통보[H0STCNI0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:396:    국내주식 실시간 체결통보 수신 시에 (1) 주문·정정·취소·거부 접수 통보 와 (2) 체결 통보 가 모두 수신됩니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:397:    (14번째 값(CNTG_YN;체결여부)가 2이면 체결통보, 1이면 주문·정정·취소·거부 접수 통보입니다.)
examples_user/domestic_stock/domestic_stock_functions_ws.py:451:# [국내주식] 실시간시세 > 국내주식 실시간체결가 (NXT)
examples_user/domestic_stock/domestic_stock_functions_ws.py:459:    국내주식 실시간체결가 (NXT)[H0NXCNT0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:460:    국내주식 실시간체결가 (NXT) API를 통해 실시간 데이터를 구독합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:467:        message (dict): 실시간 체결가 데이터 메시지
examples_user/domestic_stock/domestic_stock_functions_ws.py:512:# [국내주식] 실시간시세 > 국내주식 실시간체결가 (통합)
examples_user/domestic_stock/domestic_stock_functions_ws.py:520:    국내주식 실시간체결가 (통합)[H0UNCNT0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:521:    국내주식 실시간체결가 (통합) API를 통해 실시간 데이터를 구독합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:528:        message (dict): 실시간 체결가 데이터 메시지
examples_user/domestic_stock/domestic_stock_functions_ws.py:609:# [국내주식] 실시간시세 > 국내주식 실시간예상체결 (KRX) [실시간-041]
examples_user/domestic_stock/domestic_stock_functions_ws.py:617:    국내주식 실시간예상체결 (KRX)[H0STANC0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:618:    국내주식 실시간예상체결 API를 통해 실시간 데이터를 구독합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:702:# [국내주식] 실시간시세 > 국내주식 실시간예상체결 (NXT)
examples_user/domestic_stock/domestic_stock_functions_ws.py:710:    국내주식 실시간예상체결 (NXT)[H0NXANC0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:711:    국내주식 실시간예상체결 (NXT) API를 통해 실시간 데이터를 구독합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:798:# [국내주식] 실시간시세 > 국내주식 실시간예상체결(통합)
examples_user/domestic_stock/domestic_stock_functions_ws.py:806:    국내주식 실시간예상체결 (통합)[H0UNANC0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:807:    국내주식 실시간예상체결 (통합) API입니다. 이 함수는 웹소켓을 통해 실시간 데이터를 구독하거나 구독 해제합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:891:# [국내주식] 실시간시세 > 국내지수 실시간체결 [실시간-026]
examples_user/domestic_stock/domestic_stock_functions_ws.py:899:    국내지수 실시간체결[H0UPCNT0] 구독 함수
examples_user/domestic_stock/domestic_stock_functions_ws.py:950:# [국내주식] 실시간시세 > 국내지수 실시간예상체결 [실시간-027]
examples_user/domestic_stock/domestic_stock_functions_ws.py:958:    국내지수 실시간예상체결[H0UPANC0] 구독 함수
examples_user/domestic_stock/domestic_stock_functions_ws.py:1757:# [국내주식] 실시간시세 > 국내주식 시간외 실시간체결가 (KRX) [실시간-042]
examples_user/domestic_stock/domestic_stock_functions_ws.py:1765:    국내주식 시간외 실시간체결가 (KRX)[H0STOUP0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:1766:    국내주식 시간외 실시간체결가 API입니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:1767:    국내주식 시간외 단일가(16:00~18:00) 시간대에 실시간체결가 데이터 확인 가능합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:1853:# [국내주식] 실시간시세 > 국내주식 시간외 실시간예상체결 (KRX) [실시간-024]
examples_user/domestic_stock/domestic_stock_functions_ws.py:1861:    국내주식 시간외 실시간예상체결 (KRX)[H0STOAC0]
examples_user/domestic_stock/domestic_stock_functions_ws.py:1862:    국내주식 시간외 단일가(16:00~18:00) 시간대에 실시간예상체결 데이터를 구독합니다.
examples_user/domestic_stock/domestic_stock_functions_ws.py:1994:        "stck_cntg_hour",  # 주식체결시간
examples_user/domestic_stock/domestic_stock_functions_ws.py:1995:        "seln_cnqn",       # 매도체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:1997:        "shnu_cnqn",       # 매수2체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:1999:        "ntby_cnqn",       # 순매수체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:2054:        "STCK_CNTG_HOUR",  # 주식 체결 시간
examples_user/domestic_stock/domestic_stock_functions_ws.py:2055:        "SELN_CNQN",       # 매도 체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:2057:        "SHNU_CNQN",       # 매수2 체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:2059:        "NTBY_CNQN",       # 순매수 체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:2116:        "STCK_CNTG_HOUR",  # 주식 체결 시간
examples_user/domestic_stock/domestic_stock_functions_ws.py:2117:        "SELN_CNQN",       # 매도 체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:2119:        "SHNU_CNQN",       # 매수2 체결량
examples_user/domestic_stock/domestic_stock_functions_ws.py:2121:        "NTBY_CNQN",       # 순매수 체결량
examples_llm/elw/indicator_trend_daily/chk_indicator_trend_daily.py:21:# [국내주식] ELW시세 - ELW 투자지표추이(일별)[국내주식-173]
examples_llm/elw/indicator_trend_daily/chk_indicator_trend_daily.py:50:    ELW 투자지표추이(일별)[국내주식-173]
examples_llm/elw/indicator_trend_daily/chk_indicator_trend_daily.py:52:    ELW 투자지표추이(일별) 테스트 함수
examples_llm/elw/indicator_trend_daily/chk_indicator_trend_daily.py:58:        - DataFrame: ELW 투자지표추이(일별) 결과
examples_llm/elw/indicator_trend_daily/chk_indicator_trend_daily.py:98:        logger.info("=== ELW 투자지표추이(일별) 결과 ===")
examples_user/overseas_stock/overseas_stock_examples_ws.py:29:# [해외주식] 실시간시세 > 해외주식 실시간체결통보[실시간-009]
examples_user/overseas_stock/overseas_stock_examples_ws.py:41:# [해외주식] 실시간시세 > 해외주식 실시간지연체결가[실시간-007]
examples_user/domestic_stock/domestic_stock_examples_ws.py:41:# [국내주식] 실시간시세 > 국내주식 실시간체결가(KRX) [실시간-003]
examples_user/domestic_stock/domestic_stock_examples_ws.py:47:# [국내주식] 실시간시세 > 국내주식 주식체결통보 [실시간-005]
examples_user/domestic_stock/domestic_stock_examples_ws.py:53:# [국내주식] 실시간시세 > 국내주식 실시간체결가 (NXT)
examples_user/domestic_stock/domestic_stock_examples_ws.py:59:# [국내주식] 실시간시세 > 국내주식 실시간체결가 (통합)
examples_user/domestic_stock/domestic_stock_examples_ws.py:65:# [국내주식] 실시간시세 > 국내주식 실시간예상체결 (KRX) [실시간-041]
examples_user/domestic_stock/domestic_stock_examples_ws.py:71:# [국내주식] 실시간시세 > 국내주식 실시간예상체결 (NXT)
examples_user/domestic_stock/domestic_stock_examples_ws.py:80:# [국내주식] 실시간시세 > 국내주식 실시간예상체결(통합)
examples_user/domestic_stock/domestic_stock_examples_ws.py:86:# [국내주식] 실시간시세 > 국내지수 실시간체결 [실시간-026]
examples_user/domestic_stock/domestic_stock_examples_ws.py:92:# [국내주식] 실시간시세 > 국내지수 실시간예상체결 [실시간-027]
examples_user/domestic_stock/domestic_stock_examples_ws.py:146:# [국내주식] 실시간시세 > 국내주식 시간외 실시간체결가 (KRX) [실시간-042]
examples_user/domestic_stock/domestic_stock_examples_ws.py:152:# [국내주식] 실시간시세 > 국내주식 시간외 실시간예상체결 (KRX) [실시간-024]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:12:# [국내선물옵션] 실시간시세 > 상품선물 실시간체결가[실시간-022]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:20:    상품선물 실시간체결가 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:21:    실시간 웹소켓 연결을 통해 상품선물의 실시간 체결가 정보를 수신할 수 있습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:22:    현재가, 시고저가, 체결량, 누적거래량, 이론가, 베이시스, 괴리율 등의 상세 정보를 제공합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:23:    매도/매수 호가, 체결 건수, 미결제 약정 수량 등의 선물거래 필수 정보를 포함합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:192:# [국내선물옵션] 실시간시세 > 선물옵션 실시간체결통보[실시간-012]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:200:    선물옵션 실시간체결통보 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:201:    실시간 웹소켓 연결을 통해 선물옵션 거래의 실시간 체결 통보를 수신할 수 있습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:202:    주문접수, 체결, 정정, 취소 등의 거래 상태 변화를 실시간으로 통보받을 수 있습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:203:    고객ID, 계좌번호, 주문번호, 체결수량, 체결단가 등의 상세 거래 정보를 포함합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:258:# [국내선물옵션] 실시간시세 > 주식선물 실시간예상체결 [실시간-031]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:266:    [국내선물옵션] 실시간시세 > 주식선물 실시간예상체결 [실시간-031]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:310:# [국내선물옵션] 실시간시세 > 지수선물 실시간체결가[실시간-010]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:318:    지수선물 실시간체결가 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:319:    실시간 웹소켓 연결을 통해 지수선물의 실시간 체결가 정보를 수신할 수 있습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:320:    현재가, 시고저가, 체결량, 누적거래량, 이론가, 베이시스, 괴리율 등의 상세 정보를 제공합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:321:    매도/매수 호가, 체결 건수, 미결제 약정 수량 등의 선물거래 필수 정보를 포함합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:492:# [국내선물옵션] 실시간시세 > 지수옵션 실시간체결가[실시간-014]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:500:    지수옵션 실시간체결가 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:501:    실시간 웹소켓 연결을 통해 지수옵션의 실시간 체결가 정보를 수신할 수 있습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:502:    옵션 현재가, 시고저가, 체결량, 누적거래량, 이론가 등의 기본 정보와 함께
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:504:    옵션 거래에 필수적인 전문 지표들을 포함하는 확장된 체결가 정보입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:771:# [국내선물옵션] 실시간시세 > KRX야간선물 실시간종목체결 [실시간-064]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:866:# [국내선물옵션] 실시간시세 > KRX야간선물 실시간체결통보 [실시간-066]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1015:# [국내선물옵션] 실시간시세 > KRX야간옵션 실시간체결가 [실시간-032]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1117:# [국내선물옵션] 실시간시세 > KRX야간옵션실시간예상체결 [실시간-034]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1126:    KRX야간옵션실시간예상체결 [실시간-034]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1174:# [국내선물옵션] 실시간시세 > KRX야간옵션실시간체결통보 [실시간-067]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1239:# [국내선물옵션] 실시간시세 > 주식옵션 실시간예상체결 [실시간-046]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1248:    주식옵션 실시간예상체결 [실시간-046]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1291:# [국내선물옵션] 실시간시세 > 주식선물 실시간체결가 [실시간-029]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1299:    주식선물 실시간체결가 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1300:    실시간 웹소켓 연결을 통해 주식선물의 실시간 체결가 정보를 수신할 수 있습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1301:    주식 현재가, 시고저가, 체결량, 누적거래량, 이론가, 베이시스, 괴리율 등의 상세 정보를 제공합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1302:    매도/매수 호가, 체결 건수, 미결제 약정 수량 등의 선물거래 필수 정보를 포함합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1615:# [국내선물옵션] 실시간시세 > 주식옵션 실시간체결가 [실시간-044]
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:1623:    주식옵션 실시간체결가 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:268:# [국내선물옵션] 기본시세 > 선물옵션 일중예상체결추이[국내선물-018]
examples_user/domestic_futureoption/domestic_futureoption_functions.py:276:    선물옵션 일중예상체결추이 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:277:    한국투자 HTS(eFriend Plus) > [0548] 선물옵션 예상체결추이 화면의 기능을 API로 개발한 사항입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:298:    tr_id = "FHPIF05110100"  # 선물옵션 일중예상체결추이
examples_user/domestic_futureoption/domestic_futureoption_functions.py:640:    시장별 투자자매매동향(일별) API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:641:    한국투자 HTS(eFriend Plus) > [0404] 시장별 일별동향 화면의 기능을 API로 개발한 사항으로, 해당 화면을 참고하시면 기능을 이해하기 쉽습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:737:# [국내선물옵션] 주문/계좌 > 선물옵션 주문체결내역조회[v1_국내선물-003]
examples_user/domestic_futureoption/domestic_futureoption_functions.py:747:    ccld_nccs_dvsn: str,   # [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
examples_user/domestic_futureoption/domestic_futureoption_functions.py:761:    선물옵션 주문체결내역조회 API입니다. 한 번의 호출에 최대 100건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:770:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
examples_user/domestic_futureoption/domestic_futureoption_functions.py:784:        Tuple[pd.DataFrame, pd.DataFrame]: 주문체결내역 데이터 (output1, output2)
examples_user/domestic_futureoption/domestic_futureoption_functions.py:836:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-ccnl"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:893:# [국내선물옵션] 주문/계좌 > 선물옵션 기준일체결내역[v1_국내선물-016]
examples_user/domestic_futureoption/domestic_futureoption_functions.py:911:    선물옵션 기준일체결내역 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:928:        Tuple[pd.DataFrame, pd.DataFrame]: 선물옵션 기준일체결내역 데이터 (output1, output2)
examples_user/domestic_futureoption/domestic_futureoption_functions.py:962:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-ccnl-bstime"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1012:# [국내선물옵션] 주문/계좌 > 선물옵션기간약정수수료일별[v1_국내선물-017]
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1029:    선물옵션기간약정수수료일별 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1045:        Tuple[pd.DataFrame, pd.DataFrame]: 선물옵션기간약정수수료일별 데이터 (output1, output2)
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1073:    tr_id = "CTFO6119R"  # 선물옵션기간약정수수료일별
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1076:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-daily-amount-fee"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1192:    api_url = "/uapi/domestic-futureoption/v1/quotations/inquire-daily-fuopchartprice"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1386:# [국내선물옵션] 주문/계좌 > (야간)선물옵션 주문체결 내역조회 [국내선물-009]
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1395:    ccld_nccs_dvsn: str,                                # 체결미체결구분
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1411:    (야간)선물옵션 주문체결 내역조회 API입니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1419:        ccld_nccs_dvsn (str): [필수] 체결미체결구분 (ex. 00:전체, 01:체결, 02:미체결)
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1460:        raise ValueError("ccld_nccs_dvsn is required (e.g. '00:전체, 01:체결, 02:미체결')")
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1473:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-ngt-ccnl"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:2087:    선물옵션 주문 건에 대하여 정정 및 취소하는 API입니다. 단, 이미 체결된 건은 정정 및 취소가 불가합니다.
examples_user/domestic_futureoption/domestic_futureoption_functions.py:2139:    api_url = "/uapi/domestic-futureoption/v1/trading/order-rvsecncl"
examples_llm/elw/volatility_trend_minute/chk_volatility_trend_minute.py:26:    'stck_cntg_hour': '주식 체결 시간',
examples_user/elw/elw_examples_ws.py:29:# [국내주식] 실시간시세 - ELW 실시간체결가[실시간-061]
examples_user/elw/elw_examples_ws.py:35:# [국내주식] 실시간시세 - ELW 실시간예상체결[실시간-063]
examples_llm/overseas_futureoption/weekly_ccnl/weekly_ccnl.py:25:# [해외선물옵션] 기본시세 > 해외선물 체결추이(주간)[해외선물-017]
examples_llm/overseas_futureoption/weekly_ccnl/weekly_ccnl.py:45:    해외선물 체결추이(주간)[해외선물-017]
examples_llm/overseas_futureoption/weekly_ccnl/weekly_ccnl.py:46:    해외선물 체결추이(주간) API를 호출하여 DataFrame으로 반환합니다.
examples_llm/overseas_futureoption/weekly_ccnl/weekly_ccnl.py:64:        Tuple[pd.DataFrame, pd.DataFrame]: 해외선물 체결추이(주간) 데이터
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:23:# [국내선물옵션] 실시간시세 > 상품선물 실시간체결가[실시간-022]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:35:# [국내선물옵션] 실시간시세 > 선물옵션 실시간체결통보[실시간-012]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:41:# [국내선물옵션] 실시간시세 > 주식선물 실시간예상체결 [실시간-031]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:47:# [국내선물옵션] 실시간시세 > 지수선물 실시간체결가[실시간-010]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:59:# [국내선물옵션] 실시간시세 > 지수옵션 실시간체결가[실시간-014]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:77:# [국내선물옵션] 실시간시세 > KRX야간선물 실시간종목체결 [실시간-064]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:83:# [국내선물옵션] 실시간시세 > KRX야간선물 실시간체결통보 [실시간-066]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:95:# [국내선물옵션] 실시간시세 > KRX야간옵션 실시간체결가 [실시간-032]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:101:# [국내선물옵션] 실시간시세 > KRX야간옵션실시간예상체결 [실시간-034]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:107:# [국내선물옵션] 실시간시세 > KRX야간옵션실시간체결통보 [실시간-067]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:113:# [국내선물옵션] 실시간시세 > 주식옵션 실시간예상체결 [실시간-046]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:119:# [국내선물옵션] 실시간시세 > 주식선물 실시간체결가 [실시간-029]
examples_user/domestic_futureoption/domestic_futureoption_examples_ws.py:137:# [국내선물옵션] 실시간시세 > 주식옵션 실시간체결가 [실시간-044]
examples_user/overseas_stock/overseas_stock_examples.py:51:# [해외주식] 주문/계좌 > 해외주식 지정가체결내역조회 [해외주식-070]
examples_user/overseas_stock/overseas_stock_examples.py:66:# [해외주식] 주문/계좌 > 해외주식 주문체결내역 [v1_해외주식-007]
examples_user/overseas_stock/overseas_stock_examples.py:75:# [해외주식] 주문/계좌 > 해외주식 미체결내역 [v1_해외주식-005]
examples_user/overseas_stock/overseas_stock_examples.py:103:# [해외주식] 주문/계좌 > 해외주식 일별거래내역 [해외주식-063]
examples_user/overseas_stock/overseas_stock_examples.py:113:# [해외주식] 주문/계좌 > 해외주식 체결기준현재잔고 [v1_해외주식-008]
examples_user/overseas_stock/overseas_stock_examples.py:243:# [해외주식] 시세분석 > 해외주식 매수체결강도상위[해외주식-040]
examples_user/overseas_stock/overseas_stock_examples.py:314:# [해외주식] 기본시세 > 해외주식 체결추이[해외주식-037]
examples_user/overseas_stock/overseas_stock_examples.py:389:# [해외주식] 기본시세 > 해외주식 현재체결가[v1_해외주식-009]
examples_user/overseas_stock/overseas_stock_functions_ws.py:76:# [해외주식] 실시간시세 > 해외주식 실시간체결통보[실시간-009]
examples_user/overseas_stock/overseas_stock_functions_ws.py:85:    해외주식 실시간체결통보 API입니다.
examples_user/overseas_stock/overseas_stock_functions_ws.py:221:# [해외주식] 실시간시세 > 해외주식 실시간지연체결가[실시간-007]
examples_user/overseas_stock/overseas_stock_functions_ws.py:229:    해외주식 실시간지연체결가의 경우 기본적으로 무료시세(지연체결가)가 제공되며, 
examples_user/overseas_stock/overseas_stock_functions_ws.py:230:    아시아국가의 경우 HTS(efriend Plus) [7781] 시세신청(실시간) 화면에서 유료 서비스 신청 시 API로도 유료시세(실시간체결가)를 받아보실 수 있습니다. (24.11.29 반영)
examples_user/domestic_stock/domestic_stock_examples.py:28:# [국내주식] 순위분석 > 국내주식 대량체결건수 상위[국내주식-107]
examples_user/domestic_stock/domestic_stock_examples.py:67:# [국내주식] 시세분석 > 프로그램매매 종합현황(일별)[국내주식-115]
examples_user/domestic_stock/domestic_stock_examples.py:103:# [국내주식] 시세분석 > 국내주식 신용잔고 일별추이[국내주식-110]
examples_user/domestic_stock/domestic_stock_examples.py:111:# [국내주식] 시세분석 > 종목별 일별 대차거래추이 [국내주식-135]
examples_user/domestic_stock/domestic_stock_examples.py:123:# [국내주식] 시세분석 > 국내주식 공매도 일별추이[국내주식-134]
examples_user/domestic_stock/domestic_stock_examples.py:162:# [국내주식] 기본시세 > 국내주식 장마감 예상체결가[국내주식-120]
examples_user/domestic_stock/domestic_stock_examples.py:175:# [국내주식] 업종/기타 > 국내주식 예상체결지수 추이[국내주식-121]
examples_user/domestic_stock/domestic_stock_examples.py:182:# [국내주식] 시세분석 > 국내주식 예상체결가 추이[국내주식-118]
examples_user/domestic_stock/domestic_stock_examples.py:194:# [국내주식] 업종/기타 > 국내주식 예상체결 전체지수[국내주식-122]
examples_user/domestic_stock/domestic_stock_examples.py:203:# [국내주식] 순위분석 > 국내주식 예상체결 상승_하락상위[v1_국내주식-103]
examples_user/domestic_stock/domestic_stock_examples.py:343:# [국내주식] 기본시세 > 주식현재가 호가/예상체결[v1_국내주식-011]
examples_user/domestic_stock/domestic_stock_examples.py:388:# [국내주식] 기본시세 > 주식현재가 체결[v1_국내주식-009]
examples_user/domestic_stock/domestic_stock_examples.py:410:# [국내주식] 주문/계좌 > 주식일별주문체결조회[v1_국내주식-005]
examples_user/domestic_stock/domestic_stock_examples.py:472:# [국내주식] 시세분석 > 종목별일별매수매도체결량 [v1_국내주식-056]
examples_user/domestic_stock/domestic_stock_examples.py:537:# [국내주식] 시세분석 > 시장별 투자자매매동향(일별) [국내주식-075]
examples_user/domestic_stock/domestic_stock_examples.py:592:# [국내주식] 주문/계좌 > 기간별손익일별합산조회[v1_국내주식-052]
examples_user/domestic_stock/domestic_stock_examples.py:660:# [국내주식] 기본시세 > 주식일별분봉조회 [국내주식-213]
examples_user/domestic_stock/domestic_stock_examples.py:692:# [국내주식] 기본시세 > 주식현재가 당일시간대별체결[v1_국내주식-023]
examples_user/domestic_stock/domestic_stock_examples.py:705:# [국내주식] 기본시세 > 주식현재가 시간외시간별체결[v1_국내주식-025]
examples_user/domestic_stock/domestic_stock_examples.py:786:# [국내주식] 시세분석  > 종목별 투자자매매동향(일별)[종목별 투자자매매동향(일별)]

exec
/bin/zsh -lc 'rg "def .*daily|period|dailyprice|price|order|ccld|ccnl|inquire.*order|order_cash" examples_user/overseas_stock/overseas_stock_functions.py -n' in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
exec
/bin/zsh -lc 'rg "def .*daily|inquire_daily|daily_price|inquire_daily_price|period_price|order_cash|inquire_daily_ccld|ccnl|overseas_order|order" examples_user/domestic_stock/domestic_stock_functions.py -n' in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
624:def comp_program_trade_daily(
1019:def daily_credit_balance(
1114:def daily_loan_trans(
1172:def daily_short_sale(
3976:def inquire_ccnl(
3993:        >>> df = inquire_ccnl("real", "J", "005930")
3996:    api_url = "/uapi/domestic-stock/v1/quotations/inquire-ccnl"
4120:def inquire_daily_ccld(
4183:        >>> df1, df2 = inquire_daily_ccld(
4296:            return inquire_daily_ccld(
4314:def inquire_daily_indexchartprice(
4349:        >>> df1, df2 = inquire_daily_indexchartprice(
4357:        >>> df1, df2 = inquire_daily_indexchartprice(
4449:            return inquire_daily_indexchartprice(
4473:def inquire_daily_itemchartprice(
4499:        >>> df1, df2 = inquire_daily_itemchartprice("real", "J", "005930", "20220101", "20220809", "D", "1")
4563:def inquire_daily_overtimeprice(
4580:        >>> result1, result2 = inquire_daily_overtimeprice("real", "J", "005930")
4628:def inquire_daily_price(
4653:        >>> df = inquire_daily_price("real", "J", "005930", "D", "1")
4705:def inquire_daily_trade_volume(
4727:        >>> df1, df2 = inquire_daily_trade_volume("J", "005930", "D")
5017:def inquire_index_daily_price(
5048:        >>> df1, df2 = inquire_index_daily_price('D', 'U', '0001', '20240223')
5112:            return inquire_index_daily_price(
5484:def inquire_investor_daily_by_market(
5665:def inquire_member_daily(
6206:def inquire_psbl_order(
6247:        >>> df = inquire_psbl_order(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_unpr="55000", ord_dvsn="01", cma_evlu_amt_icld_yn="N", ovrs_icld_yn="N")
6250:    api_url = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"
6506:def inquire_time_dailychartprice(
7916:def investor_trade_by_stock_daily(
10097:def order_cash(
10143:        >>> df = order_cash(env_dv="demo", ord_dv="buy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_dvsn="00", ord_qty="1", ord_unpr="70000", excg_id_dvsn_cd="KRX")
10146:    api_url = "/uapi/domestic-stock/v1/trading/order-cash"
10220:def order_credit(
10285:        >>> df = order_credit(ord_dv="buy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", crdt_type="21", loan_dt="20220810", ord_dvsn="00", ord_qty="1", ord_unpr="55000")
10288:    api_url = "/uapi/domestic-stock/v1/trading/order-credit"
10387:def order_resv(
10452:        >>> df = order_resv(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_qty="1", ord_unpr="55000", sll_buy_dvsn_cd="02", ord_dvsn_cd="00", ord_objt_cblc_dvsn_cd="10")
10455:    api_url = "/uapi/domestic-stock/v1/trading/order-resv"
10515:def order_resv_ccnl(
10559:        >>> df = order_resv_ccnl(
10569:    api_url = "/uapi/domestic-stock/v1/trading/order-resv-ccnl"
10634:            return order_resv_ccnl(
10651:def order_resv_rvsecncl(
10697:        >>> df = order_resv_rvsecncl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, rsvn_ord_seq="88793", rsvn_ord_orgno="123", rsvn_ord_ord_dt="20250113", ord_type="cancel")
10700:    api_url = "/uapi/domestic-stock/v1/trading/order-resv-rvsecncl"
10771:def order_rvsecncl(
10813:        >>> df = order_rvsecncl(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ...)
10816:    api_url = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
11443:def pension_inquire_daily_ccld(
11480:        >>> df = pension_inquire_daily_ccld(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, user_dvsn_cd="%%", sll_buy_dvsn_cd="00", ccld_nccs_dvsn="%%", inqr_dvsn_3="00")
11540:            return pension_inquire_daily_ccld(
11679:def pension_inquire_psbl_order(
11707:        >>> df = pension_inquire_psbl_order(
11717:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-psbl-order"
12229:def program_trade_by_stock_daily(

 succeeded in 0ms:
113:def daytime_order(
114:        order_dv: str,  # 주문구분 buy(매수) / sell(매도)
133:        order_dv (str): 주문구분 buy(매수) / sell(매도)
149:        >>> df = daytime_order(
150:        ...     order_dv="buy",
190:    if order_dv == "buy":
192:    elif order_dv == "sell":
195:        logger.error("Invalid order_dv. (e.g. 'buy' or 'sell')")
196:        raise ValueError("Invalid order_dv. (e.g. 'buy' or 'sell')")
198:    api_url = "/uapi/overseas-stock/v1/trading/daytime-order"
240:def daytime_order_rvsecncl(
276:        >>> df = daytime_order_rvsecncl(
322:    api_url = "/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl"
457:def inquire_algo_ccnl(
494:        >>> result, result3 = inquire_algo_ccnl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod)
515:    api_url = "/uapi/overseas-stock/v1/trading/inquire-algo-ccnl"
551:            return inquire_algo_ccnl(
730:def inquire_ccnl(
737:        ccld_nccs_dvsn: str,  # 체결미체결구분
763:        ccld_nccs_dvsn (str): 00 : 전체  01 : 체결  02 : 미체결 ※ 모의투자계좌의 경우 "00"(전체 조회)만 가능
781:        >>> df = inquire_ccnl(
788:        ...     ccld_nccs_dvsn="00",
815:    if not ccld_nccs_dvsn:
816:        logger.error("ccld_nccs_dvsn is required. (e.g. '00')")
817:        raise ValueError("ccld_nccs_dvsn is required. (e.g. '00')")
835:    api_url = "/uapi/overseas-stock/v1/trading/inquire-ccnl"
844:        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
875:            return inquire_ccnl(
882:                ccld_nccs_dvsn=ccld_nccs_dvsn,
1219:def inquire_period_profit(
1264:        >>> df1, df2 = inquire_period_profit(
1310:    api_url = "/uapi/overseas-stock/v1/trading/inquire-period-profit"
1377:            return inquire_period_profit(
1413:def inquire_period_trans(
1456:        >>> df1, df2 = inquire_period_trans(
1498:    api_url = "/uapi/overseas-stock/v1/trading/inquire-period-trans"
1564:            return inquire_period_trans(
2137:def order(
2175:        >>> df = order(
2270:    api_url = "/uapi/overseas-stock/v1/trading/order"
2314:def order_resv(
2399:        >>> df = order_resv(env_dv="real", ord_dv="usBuy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="TSLA", ovrs_excg_cd="NASD", ft_ord_qty="1", ft_ord_unpr3="900")
2450:    api_url = "/uapi/overseas-stock/v1/trading/order-resv"
2494:def order_resv_ccnl(
2524:        >>> df = order_resv_ccnl(env_dv="real", nat_dv="us", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, rsvn_ord_rcit_dt="20220810", ovrs_rsvn_odno="0030008244")
2560:    api_url = "/uapi/overseas-stock/v1/trading/order-resv-ccnl"
2585:def order_resv_list(
2628:        >>> df = order_resv_list(nat_dv="us", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_strt_dt="20250101", inqr_end_dt="20251231", inqr_dvsn_cd="00", ovrs_excg_cd="NASD")
2668:    api_url = "/uapi/overseas-stock/v1/trading/order-resv-list"
2699:            return order_resv_list(
2716:def order_rvsecncl(
2752:        >>> df = order_rvsecncl(
2801:    api_url = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
2843:def price_fluct(
2877:        >>> df1, df2 = price_fluct(excd="NAS", gubn="0", minx="0", vol_rang="0")
2904:    api_url = "/uapi/overseas-stock/v1/ranking/price-fluct"
2937:            return price_fluct(
3749:    api_url = "/uapi/overseas-price/v1/quotations/brknews-title"
3849:    api_url = "/uapi/overseas-price/v1/quotations/colable-by-company"
4006:def dailyprice(
4043:        >>> df1, df2 = dailyprice("auth_token", "NAS", "TSLA", "0", "20230101", "0", "")
4076:    api_url = "/uapi/overseas-price/v1/quotations/dailyprice"
4137:            return dailyprice(
4165:def industry_price(
4190:        >>> df1, df2 = industry_price(excd="NAS")
4207:    api_url = "/uapi/overseas-price/v1/quotations/industry-price"
4236:            return industry_price(
4306:    api_url = "/uapi/overseas-price/v1/quotations/industry-theme"
4353:def inquire_asking_price(
4384:        >>> df1, df2, df3 = inquire_asking_price(auth="your_auth_token", excd="NAS", symb="TSLA")
4404:    api_url = "/uapi/overseas-price/v1/quotations/inquire-asking-price"
4480:            return inquire_asking_price(
4499:def quot_inquire_ccnl(
4528:        >>> df = quot_inquire_ccnl(excd="NAS", tday="0", symb="TSLA")
4550:    api_url = "/uapi/overseas-price/v1/quotations/inquire-ccnl"
4576:            return quot_inquire_ccnl(
4591:def inquire_daily_chartprice(
4596:        fid_period_div_code: str,  # FID 기간 분류 코드
4614:        fid_period_div_code (str): D:일, W:주, M:월, Y:년
4626:        >>> df1, df2 = inquire_daily_chartprice(
4631:        ...     fid_period_div_code="D",
4650:    if not fid_period_div_code:
4651:        logger.error("fid_period_div_code is required. (e.g. 'D')")
4652:        raise ValueError("fid_period_div_code is required. (e.g. 'D')")
4665:    api_url = "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"
4672:        "FID_PERIOD_DIV_CODE": fid_period_div_code,
4725:            return inquire_daily_chartprice(
4730:                fid_period_div_code,
4750:        co_yn_pricecur: str,  # 현재가선택조건
4751:        co_st_pricecur: str,  # 현재가시작범위가
4752:        co_en_pricecur: str,  # 현재가끝범위가
4789:        co_yn_pricecur (str): 해당조건 사용시(1), 미사용시 필수항목아님
4790:        co_st_pricecur (str): 단위: 각국통화(JPY, USD, HKD, CNY, VND)
4791:        co_en_pricecur (str): 단위: 각국통화(JPY, USD, HKD, CNY, VND)
4825:        ...     auth="", excd="NAS", co_yn_pricecur="1", co_st_pricecur="160", co_en_pricecur="161",
4846:    api_url = "/uapi/overseas-price/v1/quotations/inquire-search"
4851:        "CO_YN_PRICECUR": co_yn_pricecur,
4852:        "CO_ST_PRICECUR": co_st_pricecur,
4853:        "CO_EN_PRICECUR": co_en_pricecur,
4931:                co_yn_pricecur,
4932:                co_st_pricecur,
4933:                co_en_pricecur,
4971:def inquire_time_indexchartprice(
5002:        >>> df1, df2 = inquire_time_indexchartprice(
5032:    api_url = "/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice"
5089:            return inquire_time_indexchartprice(
5109:def inquire_time_itemchartprice(
5150:        >>> df1, df2 = inquire_time_itemchartprice(
5180:    api_url = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
5242:            return inquire_time_itemchartprice(
5316:    api_url = "/uapi/overseas-price/v1/quotations/news-title"
5360:def period_rights(
5398:        >>> df = period_rights("%%", "02", "20240417", "20240417")
5425:    api_url = "/uapi/overseas-price/v1/quotations/period-rights"
5455:            return period_rights(
5471:def price(
5500:        >>> df = price("", "NAS", "AAPL")
5527:    api_url = "/uapi/overseas-price/v1/quotations/price"
5557:            return price(
5577:def price_detail(
5604:        >>> df = price_detail(auth="your_auth_token", excd="NAS", symb="TSLA")
5622:    api_url = "/uapi/overseas-price/v1/quotations/price-detail"
5651:            return price_detail(
5708:    api_url = "/uapi/overseas-price/v1/quotations/rights-by-ice"
5775:    api_url = "/uapi/overseas-price/v1/quotations/search-info"

codex
There are two overseas daily-price style APIs in the official samples: `dailyprice` and `inquire-daily-chartprice`. For historical OHLCV bars, I’m checking both parameter sets so I can call out the one that best matches daily OHLCV.
exec
/bin/zsh -lc "sed -n '4591,4738p' examples_user/overseas_stock/overseas_stock_functions.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
exec
/bin/zsh -lc "sed -n '4000,4145p' examples_user/overseas_stock/overseas_stock_functions.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:


##############################################################################################
# [해외주식] 기본시세 > 해외주식 기간별시세[v1_해외주식-010]
##############################################################################################

def dailyprice(
        auth: str,  # 사용자권한정보
        excd: str,  # 거래소코드
        symb: str,  # 종목코드
        gubn: str,  # 일/주/월구분
        bymd: str,  # 조회기준일자
        modp: str,  # 수정주가반영여부
        env_dv: str = "real",  # 실전모의구분
        dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output1)
        dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output2)
        tr_cont: str = "",
        depth: int = 0,
        max_depth: int = 10
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    [해외주식] 기본시세
    해외주식 기간별시세[v1_해외주식-010]
    해외주식 기간별시세 API를 호출하여 DataFrame으로 반환합니다.

    Args:
        auth (str): 사용자권한정보 (예: "")
        excd (str): 거래소코드 (예: "NAS")
        symb (str): 종목코드 (예: "TSLA")
        gubn (str): 일/주/월구분 (예: "0")
        bymd (str): 조회기준일자(YYYYMMDD) (예: "20230101")
        modp (str): 수정주가반영여부 (예: "0")
        env_dv (str): 실전모의구분 (real:실전, demo:모의)
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
        tr_cont (str): 연속 거래 여부
        depth (int): 현재 재귀 깊이
        max_depth (int): 최대 재귀 깊이 (기본값: 10)

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 해외주식 기간별시세 데이터

    Example:
        >>> df1, df2 = dailyprice("auth_token", "NAS", "TSLA", "0", "20230101", "0", "")
        >>> print(df1)
        >>> print(df2)
    """
    # 로깅 설정
    logger = logging.getLogger(__name__)

    # 필수 파라미터 검증
    if not excd:
        logger.error("excd is required. (e.g. 'NAS')")
        raise ValueError("excd is required. (e.g. 'NAS')")
    if not symb:
        logger.error("symb is required. (e.g. 'TSLA')")
        raise ValueError("symb is required. (e.g. 'TSLA')")
    if not gubn:
        logger.error("gubn is required. (e.g. '0')")
        raise ValueError("gubn is required. (e.g. '0')")
    if not modp:
        logger.error("modp is required. (e.g. '0')")
        raise ValueError("modp is required. (e.g. '0')")

    # 최대 재귀 깊이 체크
    if depth >= max_depth:
        logger.warning("Maximum recursion depth (%d) reached. Stopping further requests.", max_depth)
        return dataframe1 if dataframe1 is not None else pd.DataFrame(), dataframe2 if dataframe2 is not None else pd.DataFrame()

    # TR ID 설정 (모의투자 지원 로직)
    if env_dv == "real" or env_dv == "demo":
        tr_id = "HHDFS76240000"  # 실전/모의투자 공통 TR ID
    else:
        logger.error("env_dv can only be 'real' or 'demo'")
        raise ValueError("env_dv can only be 'real' or 'demo'")

    api_url = "/uapi/overseas-price/v1/quotations/dailyprice"

    params = {
        "AUTH": auth,
        "EXCD": excd,
        "SYMB": symb,
        "GUBN": gubn,
        "BYMD": bymd,
        "MODP": modp,
    }

    res = ka._url_fetch(api_url, tr_id, tr_cont, params)

    if res.isOK():
        # output1 처리
        if hasattr(res.getBody(), 'output1'):
            output_data = res.getBody().output1
            if output_data:
                # output1은 단일 객체, output2는 배열일 수 있음
                if isinstance(output_data, list):
                    current_data1 = pd.DataFrame(output_data)
                else:
                    # 단일 객체인 경우 리스트로 감싸서 DataFrame 생성
                    current_data1 = pd.DataFrame([output_data])

                if dataframe1 is not None:
                    dataframe1 = pd.concat([dataframe1, current_data1], ignore_index=True)
                else:
                    dataframe1 = current_data1
            else:
                if dataframe1 is None:
                    dataframe1 = pd.DataFrame()
        else:
            if dataframe1 is None:
                dataframe1 = pd.DataFrame()
        # output2 처리
        if hasattr(res.getBody(), 'output2'):
            output_data = res.getBody().output2
            if output_data:
                # output1은 단일 객체, output2는 배열일 수 있음
                if isinstance(output_data, list):
                    current_data2 = pd.DataFrame(output_data)
                else:
                    # 단일 객체인 경우 리스트로 감싸서 DataFrame 생성
                    current_data2 = pd.DataFrame([output_data])

                if dataframe2 is not None:
                    dataframe2 = pd.concat([dataframe2, current_data2], ignore_index=True)
                else:
                    dataframe2 = current_data2
            else:
                if dataframe2 is None:
                    dataframe2 = pd.DataFrame()
        else:
            if dataframe2 is None:
                dataframe2 = pd.DataFrame()
        tr_cont = res.getHeader().tr_cont

        if tr_cont in ["M", "F"]:
            logger.info("Calling next page...")
            ka.smart_sleep()
            return dailyprice(
                auth,
                excd,
                symb,
                gubn,
                bymd,
                modp,
                env_dv,
                dataframe1,

 succeeded in 0ms:
def inquire_daily_chartprice(
        fid_cond_mrkt_div_code: str,  # FID 조건 시장 분류 코드
        fid_input_iscd: str,  # FID 입력 종목코드
        fid_input_date_1: str,  # FID 입력 날짜1
        fid_input_date_2: str,  # FID 입력 날짜2
        fid_period_div_code: str,  # FID 기간 분류 코드
        env_dv: str = "real",  # 실전모의구분
        dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output1)
        dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output2)
        tr_cont: str = "",
        depth: int = 0,
        max_depth: int = 10
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    [해외주식] 기본시세
    해외주식 종목_지수_환율기간별시세(일_주_월_년)[v1_해외주식-012]
    해외주식 종목_지수_환율기간별시세(일_주_월_년) API를 호출하여 DataFrame으로 반환합니다.

    Args:
        fid_cond_mrkt_div_code (str): N: 해외지수, X 환율, I: 국채, S:금선물
        fid_input_iscd (str): 종목코드 ※ 해외주식 마스터 코드 참조  (포럼 > FAQ > 종목정보 다운로드(해외) > 해외지수)  ※ 해당 API로 미국주식 조회 시, 다우30, 나스닥100, S&P500 종목만 조회 가능합니다. 더 많은 미국주식 종목 시세를 이용할 시에는, 해외주식기간별시세 API 사용 부탁드립니다.
        fid_input_date_1 (str): 시작일자(YYYYMMDD)
        fid_input_date_2 (str): 종료일자(YYYYMMDD)
        fid_period_div_code (str): D:일, W:주, M:월, Y:년
        env_dv (str): 실전모의구분 (real:실전, demo:모의)
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
        tr_cont (str): 연속 거래 여부
        depth (int): 현재 재귀 깊이
        max_depth (int): 최대 재귀 깊이 (기본값: 10)

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: 해외주식 종목_지수_환율기간별시세(일_주_월_년) 데이터

    Example:
        >>> df1, df2 = inquire_daily_chartprice(
        ...     fid_cond_mrkt_div_code="N",
        ...     fid_input_iscd=".DJI",
        ...     fid_input_date_1="20220401",
        ...     fid_input_date_2="20220613",
        ...     fid_period_div_code="D",
        ...     env_dv="real"
        ... )
        >>> print(df1)
        >>> print(df2)
    """
    # [필수 파라미터 검증]
    if not fid_cond_mrkt_div_code:
        logger.error("fid_cond_mrkt_div_code is required. (e.g. 'N')")
        raise ValueError("fid_cond_mrkt_div_code is required. (e.g. 'N')")
    if not fid_input_iscd:
        logger.error("fid_input_iscd is required. (e.g. '.DJI')")
        raise ValueError("fid_input_iscd is required. (e.g. '.DJI')")
    if not fid_input_date_1:
        logger.error("fid_input_date_1 is required. (e.g. '20220401')")
        raise ValueError("fid_input_date_1 is required. (e.g. '20220401')")
    if not fid_input_date_2:
        logger.error("fid_input_date_2 is required. (e.g. '20220613')")
        raise ValueError("fid_input_date_2 is required. (e.g. '20220613')")
    if not fid_period_div_code:
        logger.error("fid_period_div_code is required. (e.g. 'D')")
        raise ValueError("fid_period_div_code is required. (e.g. 'D')")

    # 최대 재귀 깊이 체크
    if depth >= max_depth:
        logger.warning("Maximum recursion depth (%d) reached. Stopping further requests.", max_depth)
        return dataframe1 if dataframe1 is not None else pd.DataFrame(), dataframe2 if dataframe2 is not None else pd.DataFrame()

    # TR ID 설정 (모의투자 지원 로직)
    if env_dv == "real" or env_dv == "demo":
        tr_id = "FHKST03030100"  # 실전투자용 TR ID
    else:
        raise ValueError("env_dv can only be 'real' or 'demo'")

    api_url = "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"

    params = {
        "FID_COND_MRKT_DIV_CODE": fid_cond_mrkt_div_code,
        "FID_INPUT_ISCD": fid_input_iscd,
        "FID_INPUT_DATE_1": fid_input_date_1,
        "FID_INPUT_DATE_2": fid_input_date_2,
        "FID_PERIOD_DIV_CODE": fid_period_div_code,
    }

    res = ka._url_fetch(api_url, tr_id, tr_cont, params)

    if res.isOK():
        # output1 처리
        if hasattr(res.getBody(), 'output1'):
            output_data = res.getBody().output1
            if output_data:
                # output1은 단일 객체, output2는 배열일 수 있음
                if isinstance(output_data, list):
                    current_data1 = pd.DataFrame(output_data)
                else:
                    # 단일 객체인 경우 리스트로 감싸서 DataFrame 생성
                    current_data1 = pd.DataFrame([output_data])

                if dataframe1 is not None:
                    dataframe1 = pd.concat([dataframe1, current_data1], ignore_index=True)
                else:
                    dataframe1 = current_data1
            else:
                if dataframe1 is None:
                    dataframe1 = pd.DataFrame()
        else:
            if dataframe1 is None:
                dataframe1 = pd.DataFrame()
        # output2 처리
        if hasattr(res.getBody(), 'output2'):
            output_data = res.getBody().output2
            if output_data:
                # output1은 단일 객체, output2는 배열일 수 있음
                if isinstance(output_data, list):
                    current_data2 = pd.DataFrame(output_data)
                else:
                    # 단일 객체인 경우 리스트로 감싸서 DataFrame 생성
                    current_data2 = pd.DataFrame([output_data])

                if dataframe2 is not None:
                    dataframe2 = pd.concat([dataframe2, current_data2], ignore_index=True)
                else:
                    dataframe2 = current_data2
            else:
                if dataframe2 is None:
                    dataframe2 = pd.DataFrame()
        else:
            if dataframe2 is None:
                dataframe2 = pd.DataFrame()
        tr_cont = res.getHeader().tr_cont

        if tr_cont in ["M", "F"]:
            logger.info("Calling next page...")
            ka.smart_sleep()
            return inquire_daily_chartprice(
                fid_cond_mrkt_div_code,
                fid_input_iscd,
                fid_input_date_1,
                fid_input_date_2,
                fid_period_div_code,
                env_dv,
                "N", dataframe1, dataframe2, depth + 1, max_depth
            )
        else:
            logger.info("Data fetch complete.")
            return dataframe1, dataframe2
    else:
        logger.error("API call failed: %s - %s", res.getErrorCode(), res.getErrorMessage())

exec
/bin/zsh -lc "sed -n '4473,4558p' examples_user/domestic_stock/domestic_stock_functions.py && sed -n '4628,4699p' examples_user/domestic_stock/domestic_stock_functions.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
def inquire_daily_itemchartprice(
        env_dv: str,  # 실전모의구분
        fid_cond_mrkt_div_code: str,  # 조건 시장 분류 코드
        fid_input_iscd: str,  # 입력 종목코드
        fid_input_date_1: str,  # 입력 날짜 1
        fid_input_date_2: str,  # 입력 날짜 2
        fid_period_div_code: str,  # 기간분류코드
        fid_org_adj_prc: str  # 수정주가 원주가 가격 여부
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    국내주식기간별시세(일/주/월/년) API입니다.
    실전계좌/모의계좌의 경우, 한 번의 호출에 최대 100건까지 확인 가능합니다.
    
    Args:
        env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
        fid_cond_mrkt_div_code (str): [필수] 조건 시장 분류 코드 (ex. J:KRX, NX:NXT, UN:통합)
        fid_input_iscd (str): [필수] 입력 종목코드 (ex. 종목코드 (ex 005930 삼성전자))
        fid_input_date_1 (str): [필수] 입력 날짜 1 (ex. 조회 시작일자)
        fid_input_date_2 (str): [필수] 입력 날짜 2 (ex. 조회 종료일자 (최대 100개))
        fid_period_div_code (str): [필수] 기간분류코드 (ex. D:일봉 W:주봉, M:월봉, Y:년봉)
        fid_org_adj_prc (str): [필수] 수정주가 원주가 가격 여부 (ex. 0:수정주가 1:원주가)

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터, output2 데이터)
        
    Example:
        >>> df1, df2 = inquire_daily_itemchartprice("real", "J", "005930", "20220101", "20220809", "D", "1")
        >>> print(df1)
        >>> print(df2)
    """
    api_url = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"

    # 필수 파라미터 검증
    if env_dv == "":
        raise ValueError("env_dv is required (e.g. 'real:실전, demo:모의')")

    if fid_cond_mrkt_div_code == "":
        raise ValueError("fid_cond_mrkt_div_code is required (e.g. 'J:KRX, NX:NXT, UN:통합')")

    if fid_input_iscd == "":
        raise ValueError("fid_input_iscd is required (e.g. '종목코드 (ex 005930 삼성전자)')")

    if fid_input_date_1 == "":
        raise ValueError("fid_input_date_1 is required (e.g. '조회 시작일자')")

    if fid_input_date_2 == "":
        raise ValueError("fid_input_date_2 is required (e.g. '조회 종료일자 (최대 100개)')")

    if fid_period_div_code == "":
        raise ValueError("fid_period_div_code is required (e.g. 'D:일봉 W:주봉, M:월봉, Y:년봉')")

    if fid_org_adj_prc == "":
        raise ValueError("fid_org_adj_prc is required (e.g. '0:수정주가 1:원주가')")

    # TR_ID 설정
    if env_dv == "real":
        tr_id = "FHKST03010100"
    elif env_dv == "demo":
        tr_id = "FHKST03010100"
    else:
        raise ValueError("env_dv is required (e.g. 'real' or 'demo')")

    params = {
        "FID_COND_MRKT_DIV_CODE": fid_cond_mrkt_div_code,
        "FID_INPUT_ISCD": fid_input_iscd,
        "FID_INPUT_DATE_1": fid_input_date_1,
        "FID_INPUT_DATE_2": fid_input_date_2,
        "FID_PERIOD_DIV_CODE": fid_period_div_code,
        "FID_ORG_ADJ_PRC": fid_org_adj_prc
    }

    res = ka._url_fetch(api_url, tr_id, "", params)

    if res.isOK():
        # output1 처리 (object 타입이므로 DataFrame)
        output1_data = pd.DataFrame([res.getBody().output1])

        # output2 처리 (array 타입이므로 DataFrame)
        output2_data = pd.DataFrame(res.getBody().output2)

        return (output1_data, output2_data)
    else:
        res.printError(url=api_url)
        return (pd.DataFrame(), pd.DataFrame())


def inquire_daily_price(
        env_dv: str,  # [필수] 실전모의구분 (ex. real:실전, demo:모의)
        fid_cond_mrkt_div_code: str,  # [필수] 조건 시장 분류 코드 (ex. J:KRX, NX:NXT, UN:통합)
        fid_input_iscd: str,  # [필수] 입력 종목코드 (ex. 종목코드 (ex 005930 삼성전자))
        fid_period_div_code: str,  # [필수] 기간 분류 코드 (ex. D:(일)최근 30거래일, W:(주)최근 30주, M:(월)최근 30개월)
        fid_org_adj_prc: str
        # [필수] 수정주가 원주가 가격 (ex. 0:수정주가미반영, 1:수정주가반영, *수정주가는 액면분할/액면병합 등 권리 발생 시 과거 시세를 현재 주가에 맞게 보정한 가격)
) -> pd.DataFrame:
    """
    주식현재가 일자별 API입니다. 일/주/월별 주가를 확인할 수 있으며 최근 30일(주,별)로 제한되어 있습니다.
    
    Args:
        env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
        fid_cond_mrkt_div_code (str): [필수] 조건 시장 분류 코드 (ex. J:KRX, NX:NXT, UN:통합)  
        fid_input_iscd (str): [필수] 입력 종목코드 (ex. 종목코드 (ex 005930 삼성전자))
        fid_period_div_code (str): [필수] 기간 분류 코드 (ex. D:(일)최근 30거래일, W:(주)최근 30주, M:(월)최근 30개월)
        fid_org_adj_prc (str): [필수] 수정주가 원주가 가격 (ex. 0:수정주가미반영, 1:수정주가반영, *수정주가는 액면분할/액면병합 등 권리 발생 시 과거 시세를 현재 주가에 맞게 보정한 가격)

    Returns:
        pd.DataFrame: 주식현재가 일자별 데이터
        
    Raises:
        ValueError: 필수 파라미터가 누락된 경우
        
    Example:
        >>> df = inquire_daily_price("real", "J", "005930", "D", "1")
        >>> print(df)
    """
    api_url = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"

    # 필수 파라미터 검증
    if env_dv == "" or env_dv is None:
        raise ValueError("env_dv is required (e.g. 'real:실전, demo:모의')")

    if fid_cond_mrkt_div_code == "" or fid_cond_mrkt_div_code is None:
        raise ValueError("fid_cond_mrkt_div_code is required (e.g. 'J:KRX, NX:NXT, UN:통합')")

    if fid_input_iscd == "" or fid_input_iscd is None:
        raise ValueError("fid_input_iscd is required (e.g. '종목코드 (ex 005930 삼성전자)')")

    if fid_period_div_code == "" or fid_period_div_code is None:
        raise ValueError("fid_period_div_code is required (e.g. 'D:(일)최근 30거래일, W:(주)최근 30주, M:(월)최근 30개월')")

    if fid_org_adj_prc == "" or fid_org_adj_prc is None:
        raise ValueError(
            "fid_org_adj_prc is required (e.g. '0:수정주가미반영, 1:수정주가반영, *수정주가는 액면분할/액면병합 등 권리 발생 시 과거 시세를 현재 주가에 맞게 보정한 가격')")

    # tr_id 설정 (실전/모의 모두 동일)
    if env_dv == "real":
        tr_id = "FHKST01010400"
    elif env_dv == "demo":
        tr_id = "FHKST01010400"
    else:
        raise ValueError("env_dv can only be real or demo")

    params = {
        "FID_COND_MRKT_DIV_CODE": fid_cond_mrkt_div_code,
        "FID_INPUT_ISCD": fid_input_iscd,
        "FID_PERIOD_DIV_CODE": fid_period_div_code,
        "FID_ORG_ADJ_PRC": fid_org_adj_prc
    }

    res = ka._url_fetch(api_url, tr_id, "", params)

    if res.isOK():
        # output은 array 자료형이므로 DataFrame으로 변환
        current_data = pd.DataFrame(res.getBody().output)
        return current_data
    else:
        res.printError(url=api_url)
        return pd.DataFrame()


exec
/bin/zsh -lc "sed -n '2137,2310p' examples_user/overseas_stock/overseas_stock_functions.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
def order(
        cano: str,  # 종합계좌번호
        acnt_prdt_cd: str,  # 계좌상품코드
        ovrs_excg_cd: str,  # 해외거래소코드
        pdno: str,  # 상품번호
        ord_qty: str,  # 주문수량
        ovrs_ord_unpr: str,  # 해외주문단가
        ord_dv: str,  # 주문구분 (buy: 매수, sell: 매도)
        ctac_tlno: str,  # 연락전화번호
        mgco_aptm_odno: str,  # 운용사지정주문번호
        ord_svr_dvsn_cd: str,  # 주문서버구분코드
        ord_dvsn: str,  # 주문구분
        env_dv: str = "real",  # 실전모의구분

) -> Optional[pd.DataFrame]:
    """
    [해외주식] 주문/계좌 
    해외주식 주문[v1_해외주식-001]
    해외주식 주문 API를 호출하여 DataFrame으로 반환합니다.
    
    Args:
        cano (str): 계좌번호 체계(8-2)의 앞 8자리
        acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
        ovrs_excg_cd (str): NASD : 나스닥 NYSE : 뉴욕 AMEX : 아멕스 SEHK : 홍콩 SHAA : 중국상해 SZAA : 중국심천 TKSE : 일본 HASE : 베트남 하노이 VNSE : 베트남 호치민
        pdno (str): 종목코드
        ord_qty (str): 주문수량 (해외거래소 별 최소 주문수량 및 주문단위 확인 필요)
        ovrs_ord_unpr (str): 1주당 가격 * 시장가의 경우 1주당 가격을 공란으로 비우지 않음 "0"으로 입력
        ord_dv (str): 주문구분 (buy: 매수, sell: 매도)
        ctac_tlno (str): 
        mgco_aptm_odno (str): 
        ord_svr_dvsn_cd (str): "0"(Default)
        ord_dvsn (str): [Header tr_id TTTT1002U(미국 매수 주문)] 00 : 지정가 32 : LOO(장개시지정가) 34 : LOC(장마감지정가) * 모의투자 VTTT1002U(미국 매수 주문)로는 00:지정가만 가능  [Header tr_id TTTT1006U(미국 매도 주문)] 00 : 지정가 31 : MOO(장개시시장가) 32 : LOO(장개시지정가) 33 : MOC(장마감시장가) 34 : LOC(장마감지정가) * 모의투자 VTTT1006U(미국 매도 주문)로는 00:지정가만 가능  [Header tr_id TTTS1001U(홍콩 매도 주문)] 00 : 지정가 50 : 단주지정가 * 모의투자 VTTS1001U(홍콩 매도 주문)로는 00:지정가만 가능  [그외 tr_id] 제거
        env_dv (str): 실전모의구분 (real:실전, demo:모의)
        
    Returns:
        Optional[pd.DataFrame]: 해외주식 주문 데이터
        
    Example:
        >>> df = order(
        ...     cano=trenv.my_acct,
        ...     acnt_prdt_cd=trenv.my_prod,
        ...     ovrs_excg_cd="NASD",
        ...     pdno="AAPL",
        ...     ord_qty="1",
        ...     ovrs_ord_unpr="145.00",
        ...     ord_dv="buy",
        ...     ctac_tlno="",
        ...     mgco_aptm_odno="",
        ...     ord_svr_dvsn_cd="0",
        ...     ord_dvsn="00",
        ...     env_dv="real"
        ... )
        >>> print(df)
    """
    # [필수 파라미터 검증]
    if not cano:
        logger.error("cano is required. (e.g. '810XXXXX')")
        raise ValueError("cano is required. (e.g. '810XXXXX')")
    if not acnt_prdt_cd:
        logger.error("acnt_prdt_cd is required. (e.g. '01')")
        raise ValueError("acnt_prdt_cd is required. (e.g. '01')")
    if not ovrs_excg_cd:
        logger.error("ovrs_excg_cd is required. (e.g. 'NASD')")
        raise ValueError("ovrs_excg_cd is required. (e.g. 'NASD')")
    if not pdno:
        logger.error("pdno is required. (e.g. 'AAPL')")
        raise ValueError("pdno is required. (e.g. 'AAPL')")
    if not ord_qty:
        logger.error("ord_qty is required. (e.g. '1')")
        raise ValueError("ord_qty is required. (e.g. '1')")
    if not ovrs_ord_unpr:
        logger.error("ovrs_ord_unpr is required. (e.g. '145.00')")
        raise ValueError("ovrs_ord_unpr is required. (e.g. '145.00')")
    if not ord_dv:
        logger.error("ord_dv is required. (e.g. 'buy' or 'sell')")
        raise ValueError("ord_dv is required. (e.g. 'buy' or 'sell')")
    if not ord_svr_dvsn_cd:
        logger.error("ord_svr_dvsn_cd is required. (e.g. '0')")
        raise ValueError("ord_svr_dvsn_cd is required. (e.g. '0')")
    if not ord_dvsn:
        logger.error("ord_dvsn is required. (e.g. '00')")
        raise ValueError("ord_dvsn is required. (e.g. '00')")

    # TR ID 설정 (매수/매도 및 거래소별)
    if ord_dv == "buy":
        if ovrs_excg_cd in ("NASD", "NYSE", "AMEX"):
            tr_id = "TTTT1002U"  # 미국 매수 주문 [모의투자] VTTT1002U
        elif ovrs_excg_cd == "SEHK":
            tr_id = "TTTS1002U"  # 홍콩 매수 주문 [모의투자] VTTS1002U
        elif ovrs_excg_cd == "SHAA":
            tr_id = "TTTS0202U"  # 중국상해 매수 주문 [모의투자] VTTS0202U
        elif ovrs_excg_cd == "SZAA":
            tr_id = "TTTS0305U"  # 중국심천 매수 주문 [모의투자] VTTS0305U
        elif ovrs_excg_cd == "TKSE":
            tr_id = "TTTS0308U"  # 일본 매수 주문 [모의투자] VTTS0308U
        elif ovrs_excg_cd in ("HASE", "VNSE"):
            tr_id = "TTTS0311U"  # 베트남(하노이,호치민) 매수 주문 [모의투자] VTTS0311U
        else:
            logger.error(
                "ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
            raise ValueError(
                "ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
        sll_type = ""
    elif ord_dv == "sell":
        if ovrs_excg_cd in ("NASD", "NYSE", "AMEX"):
            tr_id = "TTTT1006U"  # 미국 매도 주문 [모의투자] VTTT1006U
        elif ovrs_excg_cd == "SEHK":
            tr_id = "TTTS1001U"  # 홍콩 매도 주문 [모의투자] VTTS1001U
        elif ovrs_excg_cd == "SHAA":
            tr_id = "TTTS1005U"  # 중국상해 매도 주문 [모의투자] VTTS1005U
        elif ovrs_excg_cd == "SZAA":
            tr_id = "TTTS0304U"  # 중국심천 매도 주문 [모의투자] VTTS0304U
        elif ovrs_excg_cd == "TKSE":
            tr_id = "TTTS0307U"  # 일본 매도 주문 [모의투자] VTTS0307U
        elif ovrs_excg_cd in ("HASE", "VNSE"):
            tr_id = "TTTS0310U"  # 베트남(하노이,호치민) 매도 주문 [모의투자] VTTS0310U
        else:
            logger.error(
                "ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
            raise ValueError(
                "ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
        sll_type = "00"
    else:
        logger.error("ord_dv is required. (e.g. 'buy' or 'sell')")
        raise ValueError("ord_dv is required. (e.g. 'buy' or 'sell')")

    # 모의투자인 경우 TR ID 앞에 V 붙이기
    if env_dv == "demo":
        tr_id = "V" + tr_id[1:]
    elif env_dv != "real":
        logger.error("env_dv can only be 'real' or 'demo'")
        raise ValueError("env_dv can only be 'real' or 'demo'")

    api_url = "/uapi/overseas-stock/v1/trading/order"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "OVRS_EXCG_CD": ovrs_excg_cd,
        "PDNO": pdno,
        "ORD_QTY": ord_qty,
        "OVRS_ORD_UNPR": ovrs_ord_unpr,
        "CTAC_TLNO": ctac_tlno,
        "MGCO_APTM_ODNO": mgco_aptm_odno,
        "SLL_TYPE": sll_type,
        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
        "ORD_DVSN": ord_dvsn,
    }

    res = ka._url_fetch(api_url=api_url,
                        ptr_id=tr_id,
                        tr_cont="",
                        params=params,
                        postFlag=True
                        )

    if res.isOK():
        if hasattr(res.getBody(), 'output'):
            output_data = res.getBody().output
            if not isinstance(output_data, list):
                output_data = [output_data]
            dataframe = pd.DataFrame(output_data)
        else:
            dataframe = pd.DataFrame()

        logger.info("Data fetch complete.")
        return dataframe
    else:
        logger.error("API call failed: %s - %s", res.getErrorCode(), res.getErrorMessage())
        res.printError(api_url)
        return pd.DataFrame()


##############################################################################################

exec
/bin/zsh -lc "sed -n '10097,10205p' examples_user/domestic_stock/domestic_stock_functions.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
def order_cash(
        env_dv: str,  # 실전모의구분 (real:실전, demo:모의)
        ord_dv: str,  # 매도매수구분 (buy:매수, sell:매도)
        cano: str,  # 종합계좌번호
        acnt_prdt_cd: str,  # 계좌상품코드
        pdno: str,  # 상품번호 (종목코드)
        ord_dvsn: str,  # 주문구분
        ord_qty: str,  # 주문수량
        ord_unpr: str,  # 주문단가
        excg_id_dvsn_cd: str,  # 거래소ID구분코드
        sll_type: str = "",  # 매도유형 (매도주문 시)
        cndt_pric: str = ""  # 조건가격
) -> pd.DataFrame:
    """
    국내주식주문(현금) API 입니다.

    ※ TTC0802U(현금매수) 사용하셔서 미수매수 가능합니다. 단, 거래하시는 계좌가 증거금40%계좌로 신청이 되어있어야 가능합니다. 
    ※ 신용매수는 별도의 API가 준비되어 있습니다.

    ※ ORD_QTY(주문수량), ORD_UNPR(주문단가) 등을 String으로 전달해야 함에 유의 부탁드립니다.

    ※ ORD_UNPR(주문단가)가 없는 주문은 상한가로 주문금액을 선정하고 이후 체결이되면 체결금액로 정산됩니다.

    ※ POST API의 경우 BODY값의 key값들을 대문자로 작성하셔야 합니다.
    (EX. "CANO" : "12345678", "ACNT_PRDT_CD": "01",...)

    ※ 종목코드 마스터파일 파이썬 정제코드는 한국투자증권 Github 참고 부탁드립니다.
    https://github.com/koreainvestment/open-trading-api/tree/main/stocks_info
    
    Args:
        env_dv (str): [필수] 실전모의구분 (real:실전, demo:모의)
        ord_dv (str): [필수] 매도매수구분 (buy:매수, sell:매도)
        cano (str): [필수] 종합계좌번호 (종합계좌번호)
        acnt_prdt_cd (str): [필수] 계좌상품코드 (상품유형코드)
        pdno (str): [필수] 상품번호 (종목코드(6자리) , ETN의 경우 7자리 입력)
        ord_dvsn (str): [필수] 주문구분
        ord_qty (str): [필수] 주문수량
        ord_unpr (str): [필수] 주문단가
        excg_id_dvsn_cd (str): [필수] 거래소ID구분코드 (KRX)
        sll_type (str): 매도유형 (매도주문 시) (01:일반매도,02:임의매매,05:대차매도)
        cndt_pric (str): 조건가격 (스탑지정가호가 주문 시 사용)

    Returns:
        pd.DataFrame: 주식주문 결과 데이터
        
    Example:
        >>> df = order_cash(env_dv="demo", ord_dv="buy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_dvsn="00", ord_qty="1", ord_unpr="70000", excg_id_dvsn_cd="KRX")
        >>> print(df)
    """
    api_url = "/uapi/domestic-stock/v1/trading/order-cash"

    # 필수 파라미터 검증
    if env_dv == "" or env_dv is None:
        raise ValueError("env_dv is required (e.g. 'real:실전, demo:모의')")

    if ord_dv == "" or ord_dv is None:
        raise ValueError("ord_dv is required (e.g. 'buy:매수, sell:매도')")

    if cano == "" or cano is None:
        raise ValueError("cano is required (e.g. '종합계좌번호')")

    if acnt_prdt_cd == "" or acnt_prdt_cd is None:
        raise ValueError("acnt_prdt_cd is required (e.g. '상품유형코드')")

    if pdno == "" or pdno is None:
        raise ValueError("pdno is required (e.g. '종목코드(6자리) , ETN의 경우 7자리 입력')")

    if ord_dvsn == "" or ord_dvsn is None:
        raise ValueError("ord_dvsn is required (e.g. '')")

    if ord_qty == "" or ord_qty is None:
        raise ValueError("ord_qty is required (e.g. '')")

    if ord_unpr == "" or ord_unpr is None:
        raise ValueError("ord_unpr is required (e.g. '')")

    if excg_id_dvsn_cd == "" or excg_id_dvsn_cd is None:
        raise ValueError("excg_id_dvsn_cd is required (e.g. 'KRX')")

    # tr_id 설정
    if env_dv == "real":
        if ord_dv == "sell":
            tr_id = "TTTC0011U"
        elif ord_dv == "buy":
            tr_id = "TTTC0012U"
        else:
            raise ValueError("ord_dv can only be sell or buy")
    elif env_dv == "demo":
        if ord_dv == "sell":
            tr_id = "VTTC0011U"
        elif ord_dv == "buy":
            tr_id = "VTTC0012U"
        else:
            raise ValueError("ord_dv can only be sell or buy")
    else:
        raise ValueError("env_dv is required (e.g. 'real' or 'demo')")

    params = {
        "CANO": cano,  # 종합계좌번호
        "ACNT_PRDT_CD": acnt_prdt_cd,  # 계좌상품코드
        "PDNO": pdno,  # 상품번호
        "ORD_DVSN": ord_dvsn,  # 주문구분
        "ORD_QTY": ord_qty,  # 주문수량
        "ORD_UNPR": ord_unpr,  # 주문단가
        "EXCG_ID_DVSN_CD": excg_id_dvsn_cd,  # 거래소ID구분코드
        "SLL_TYPE": sll_type,  # 매도유형
        "CNDT_PRIC": cndt_pric  # 조건가격
    }


exec
/bin/zsh -lc "sed -n '730,895p' examples_user/overseas_stock/overseas_stock_functions.py && sed -n '4120,4305p' examples_user/domestic_stock/domestic_stock_functions.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
def inquire_ccnl(
        cano: str,  # 종합계좌번호
        acnt_prdt_cd: str,  # 계좌상품코드
        pdno: str,  # 상품번호
        ord_strt_dt: str,  # 주문시작일자
        ord_end_dt: str,  # 주문종료일자
        sll_buy_dvsn: str,  # 매도매수구분
        ccld_nccs_dvsn: str,  # 체결미체결구분
        sort_sqn: str,  # 정렬순서
        ord_dt: str,  # 주문일자
        ord_gno_brno: str,  # 주문채번지점번호
        odno: str,  # 주문번호
        ovrs_excg_cd: str = "",  # 해외거래소코드
        NK200: str = "",  # 연속조회키200
        FK200: str = "",  # 연속조회검색조건200
        env_dv: str = "real",  # 실전모의구분
        tr_cont: str = "",
        dataframe: Optional[pd.DataFrame] = None,
        depth: int = 0,
        max_depth: int = 10
) -> Optional[pd.DataFrame]:
    """
    [해외주식] 주문/계좌 
    해외주식 주문체결내역[v1_해외주식-007]
    해외주식 주문체결내역 API를 호출하여 DataFrame으로 반환합니다.
    
    Args:
        cano (str): 계좌번호 체계(8-2)의 앞 8자리
        acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
        pdno (str): 전종목일 경우 "%" 입력 ※ 모의투자계좌의 경우 ""(전체 조회)만 가능
        ord_strt_dt (str): YYYYMMDD 형식 (현지시각 기준)
        ord_end_dt (str): YYYYMMDD 형식 (현지시각 기준)
        sll_buy_dvsn (str): 00 : 전체  01 : 매도  02 : 매수 ※ 모의투자계좌의 경우 "00"(전체 조회)만 가능
        ccld_nccs_dvsn (str): 00 : 전체  01 : 체결  02 : 미체결 ※ 모의투자계좌의 경우 "00"(전체 조회)만 가능
        ovrs_excg_cd (str): 전종목일 경우 "%" 입력 NASD : 미국시장 전체(나스닥, 뉴욕, 아멕스) NYSE : 뉴욕 AMEX : 아멕스 SEHK : 홍콩  SHAA : 중국상해 SZAA : 중국심천 TKSE : 일본 HASE : 베트남 하노이 VNSE : 베트남 호치민 ※ 모의투자계좌의 경우 ""(전체 조회)만 가능
        sort_sqn (str): DS : 정순 AS : 역순  ※ 모의투자계좌의 경우 정렬순서 사용불가(Default : DS(정순))
        ord_dt (str): "" (Null 값 설정)
        ord_gno_brno (str): "" (Null 값 설정)
        odno (str): "" (Null 값 설정) ※ 주문번호로 검색 불가능합니다. 반드시 ""(Null 값 설정) 바랍니다.
        NK200 (str): 공란 : 최초 조회시 이전 조회 Output CTX_AREA_NK200값 : 다음페이지 조회시(2번째부터)
        FK200 (str): 공란 : 최초 조회시 이전 조회 Output CTX_AREA_FK200값 : 다음페이지 조회시(2번째부터)
        env_dv (str): 실전모의구분 (real:실전, demo:모의)
        tr_cont (str): 연속 거래 여부
        dataframe (Optional[pd.DataFrame]): 누적 데이터프레임
        depth (int): 현재 재귀 깊이
        max_depth (int): 최대 재귀 깊이 (기본값: 10)
        
    Returns:
        Optional[pd.DataFrame]: 해외주식 주문체결내역 데이터
        
    Example:
        >>> df = inquire_ccnl(
        ...     cano=trenv.my_acct,
        ...     acnt_prdt_cd=trenv.my_prod,
        ...     pdno="%",
        ...     ord_strt_dt="20211027",
        ...     ord_end_dt="20211027",
        ...     sll_buy_dvsn="00",
        ...     ccld_nccs_dvsn="00",
        ...     ovrs_excg_cd="%%",
        ...     sort_sqn="DS",
        ...     ord_dt="",
        ...     ord_gno_brno="02111",
        ...     odno="",
        ...     NK200="",
        ...     FK200=""
        ... )
        >>> print(df)
    """
    # [필수 파라미터 검증]
    if not cano:
        logger.error("cano is required. (e.g. '810XXXXX')")
        raise ValueError("cano is required. (e.g. '810XXXXX')")
    if not acnt_prdt_cd:
        logger.error("acnt_prdt_cd is required. (e.g. '01')")
        raise ValueError("acnt_prdt_cd is required. (e.g. '01')")
    if not ord_strt_dt:
        logger.error("ord_strt_dt is required. (e.g. '20211027')")
        raise ValueError("ord_strt_dt is required. (e.g. '20211027')")
    if not ord_end_dt:
        logger.error("ord_end_dt is required. (e.g. '20211027')")
        raise ValueError("ord_end_dt is required. (e.g. '20211027')")
    if not sll_buy_dvsn:
        logger.error("sll_buy_dvsn is required. (e.g. '00')")
        raise ValueError("sll_buy_dvsn is required. (e.g. '00')")
    if not ccld_nccs_dvsn:
        logger.error("ccld_nccs_dvsn is required. (e.g. '00')")
        raise ValueError("ccld_nccs_dvsn is required. (e.g. '00')")
    if not sort_sqn:
        logger.error("sort_sqn is required. (e.g. 'DS')")
        raise ValueError("sort_sqn is required. (e.g. 'DS')")

    # 최대 재귀 깊이 체크
    if depth >= max_depth:
        logger.warning("Maximum recursion depth (%d) reached. Stopping further requests.", max_depth)
        return dataframe if dataframe is not None else pd.DataFrame()

    # TR ID 설정 (모의투자 지원 로직)
    if env_dv == "real":
        tr_id = "TTTS3035R"  # 실전투자용 TR ID
    elif env_dv == "demo":
        tr_id = "VTTS3035R"  # 모의투자용 TR ID
    else:
        raise ValueError("env_dv can only be 'real' or 'demo'")

    api_url = "/uapi/overseas-stock/v1/trading/inquire-ccnl"

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "PDNO": pdno,
        "ORD_STRT_DT": ord_strt_dt,
        "ORD_END_DT": ord_end_dt,
        "SLL_BUY_DVSN": sll_buy_dvsn,
        "CCLD_NCCS_DVSN": ccld_nccs_dvsn,
        "OVRS_EXCG_CD": ovrs_excg_cd,
        "SORT_SQN": sort_sqn,
        "ORD_DT": ord_dt,
        "ORD_GNO_BRNO": ord_gno_brno,
        "ODNO": odno,
        "CTX_AREA_NK200": NK200,
        "CTX_AREA_FK200": FK200,
    }

    res = ka._url_fetch(api_url=api_url, ptr_id=tr_id, tr_cont=tr_cont, params=params)

    if res.isOK():
        if hasattr(res.getBody(), 'output'):
            output_data = res.getBody().output
            if not isinstance(output_data, list):
                output_data = [output_data]
            current_data = pd.DataFrame(output_data)
        else:
            current_data = pd.DataFrame()

        if dataframe is not None:
            dataframe = pd.concat([dataframe, current_data], ignore_index=True)
        else:
            dataframe = current_data

        tr_cont, NK200, FK200 = res.getHeader().tr_cont, res.getBody().ctx_area_nk200, res.getBody().ctx_area_fk200

        if tr_cont in ["M", "F"]:
            logger.info("Calling next page...")
            ka.smart_sleep()
            return inquire_ccnl(
                cano=cano,
                acnt_prdt_cd=acnt_prdt_cd,
                pdno=pdno,
                ord_strt_dt=ord_strt_dt,
                ord_end_dt=ord_end_dt,
                sll_buy_dvsn=sll_buy_dvsn,
                ccld_nccs_dvsn=ccld_nccs_dvsn,
                ovrs_excg_cd=ovrs_excg_cd,
                sort_sqn=sort_sqn,
                ord_dt=ord_dt,
                ord_gno_brno=ord_gno_brno,
                odno=odno,
                NK200=NK200,
                FK200=FK200,
                env_dv=env_dv,
                tr_cont="N",
                dataframe=dataframe,
                depth=depth + 1,
                max_depth=max_depth
            )
def inquire_daily_ccld(
        env_dv: str,  # [필수] 실전모의구분 (real:실전, demo:모의)
        pd_dv: str,  # [필수] 3개월이전이내구분 (before:이전, inner:이내)
        cano: str,  # [필수] 종합계좌번호
        acnt_prdt_cd: str,  # [필수] 계좌상품코드
        inqr_strt_dt: str,  # [필수] 조회시작일자
        inqr_end_dt: str,  # [필수] 조회종료일자
        sll_buy_dvsn_cd: str,  # [필수] 매도매수구분코드 (00 : 전체 / 01 : 매도 / 02 : 매수)
        ccld_dvsn: str,  # [필수] 체결구분 (00 전체 / 01 체결 / 02 미체결)
        inqr_dvsn: str,  # [필수] 조회구분 (00 역순 / 01 정순)
        inqr_dvsn_3: str,  # [필수] 조회구분3 (00 전체 / 01 현금 / 02 신용 / 03 담보 / 04 대주 / 05 대여 / 06 자기융자신규/상환 / 07 유통융자신규/상환)
        pdno: str = "",  # 상품번호
        ord_gno_brno: str = "",  # 주문채번지점번호
        odno: str = "",  # 주문번호 (주문시 한국투자증권 시스템에서 채번된 주문번호)
        inqr_dvsn_1: str = "",  # 조회구분1 (없음: 전체 / 1: ELW / 2: 프리보드)
        FK100: str = "",  # 연속조회검색조건100 (공란: 최초 조회 / 이전 조회 Output 사용)
        NK100: str = "",  # 연속조회키100 (공란: 최초 조회 / 이전 조회 Output 사용)
        tr_cont: str = "",  # 연속거래여부
        excg_id_dvsn_cd: Optional[str] = "KRX",  # 거래소ID구분코드 (KRX / NXT / SOR / ALL)
        dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output1)
        dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output2)
        depth: int = 0,  # 내부 재귀깊이 (자동관리)
        max_depth: int = 10  # 최대 재귀 횟수 제한
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    주식일별주문체결조회 API입니다. 
    실전계좌의 경우, 한 번의 호출에 최대 100건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다. 
    모의계좌의 경우, 한 번의 호출에 최대 15건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다. 

    * 다만, 3개월 이전 체결내역 조회(CTSC9115R) 의 경우, 
    장중에는 많은 거래량으로 인해 순간적으로 DB가 밀렸거나 응답을 늦게 받거나 하는 등의 이슈가 있을 수 있어
    ① 가급적 장 종료 이후(15:30 이후) 조회하시고 
    ② 조회기간(INQR_STRT_DT와 INQR_END_DT 사이의 간격)을 보다 짧게 해서 조회하는 것을
    권유드립니다.
    
    Args:
        env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
        pd_dv (str): [필수] 3개월이전이내구분 (ex. before:이전, inner:이내)
        cano (str): [필수] 종합계좌번호
        acnt_prdt_cd (str): [필수] 계좌상품코드
        inqr_strt_dt (str): [필수] 조회시작일자
        inqr_end_dt (str): [필수] 조회종료일자
        sll_buy_dvsn_cd (str): [필수] 매도매수구분코드 (ex. 00 : 전체 / 01 : 매도 / 02 : 매수)
        pdno (str): 상품번호
        ccld_dvsn (str): [필수] 체결구분 (ex. 00 전체 / 01 체결 / 02 미체결)
        inqr_dvsn (str): [필수] 조회구분 (ex. 00 역순 / 01 정순)
        inqr_dvsn_3 (str): [필수] 조회구분3 (ex. 00 전체 / 01 현금 / 02 신용 / 03 담보 / 04 대주 / 05 대여 / 06 자기융자신규/상환 / 07 유통융자신규/상환)
        ord_gno_brno (str): 주문채번지점번호
        odno (str): 주문번호 (ex. 주문시 한국투자증권 시스템에서 채번된 주문번호)
        inqr_dvsn_1 (str): 조회구분1 (ex. 없음: 전체 / 1: ELW / 2: 프리보드)
        FK100 (str): 연속조회검색조건100 (ex. 공란: 최초 조회 / 이전 조회 Output 사용)
        NK100 (str): 연속조회키100 (ex. 공란: 최초 조회 / 이전 조회 Output 사용)
        tr_cont (str): 연속거래여부
        excg_id_dvsn_cd (Optional[str]): 거래소ID구분코드 (ex. KRX / NXT / SOR / ALL)
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
        depth (int): 내부 재귀깊이 (자동관리)
        max_depth (int): 최대 재귀 횟수 제한

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터프레임, output2 데이터프레임)
        
    Example:
        >>> df1, df2 = inquire_daily_ccld(
        ...     env_dv="real", pd_dv="inner", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod,
        ...     inqr_strt_dt="20220810", inqr_end_dt="20220810", 
        ...     sll_buy_dvsn_cd="00", pdno="005930", ccld_dvsn="00", 
        ...     inqr_dvsn="00", inqr_dvsn_3="00"
        ... )
        >>> print(df1)
        >>> print(df2)
    """
    api_url = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"

    # 필수 파라미터 검증
    if env_dv == "":
        raise ValueError("env_dv is required (e.g. 'real:실전', 'demo:모의')")

    if pd_dv == "":
        raise ValueError("pd_dv is required (e.g. 'before:이전', 'inner:이내')")

    if cano == "":
        raise ValueError("cano is required")

    if acnt_prdt_cd == "":
        raise ValueError("acnt_prdt_cd is required")

    if inqr_strt_dt == "":
        raise ValueError("inqr_strt_dt is required")

    if inqr_end_dt == "":
        raise ValueError("inqr_end_dt is required")

    if sll_buy_dvsn_cd == "":
        raise ValueError("sll_buy_dvsn_cd is required (e.g. '00 : 전체 / 01 : 매도 / 02 : 매수')")

    if ccld_dvsn == "":
        raise ValueError("ccld_dvsn is required (e.g. '00 전체 / 01 체결 / 02 미체결')")

    if inqr_dvsn == "":
        raise ValueError("inqr_dvsn is required (e.g. '00 역순 / 01 정순')")

    if inqr_dvsn_3 == "":
        raise ValueError(
            "inqr_dvsn_3 is required (e.g. '00 전체 / 01 현금 / 02 신용 / 03 담보 / 04 대주 / 05 대여 / 06 자기융자신규/상환 / 07 유통융자신규/상환')")

    if depth > max_depth:
        logging.warning("Max recursive depth reached.")
        if dataframe1 is None:
            dataframe1 = pd.DataFrame()
        if dataframe2 is None:
            dataframe2 = pd.DataFrame()
        return dataframe1, dataframe2

    # tr_id 설정
    if env_dv == "real":
        if pd_dv == "before":
            tr_id = "CTSC9215R"
        elif pd_dv == "inner":
            tr_id = "TTTC0081R"
        else:
            raise ValueError("pd_dv can only be 'before' or 'inner'")
    elif env_dv == "demo":
        if pd_dv == "before":
            tr_id = "VTSC9215R"
        elif pd_dv == "inner":
            tr_id = "VTTC0081R"
        else:
            raise ValueError("pd_dv can only be 'before' or 'inner'")
    else:
        raise ValueError("env_dv is required (e.g. 'real' or 'demo')")

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "INQR_STRT_DT": inqr_strt_dt,
        "INQR_END_DT": inqr_end_dt,
        "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
        "PDNO": pdno,
        "CCLD_DVSN": ccld_dvsn,
        "INQR_DVSN": inqr_dvsn,
        "INQR_DVSN_3": inqr_dvsn_3,
        "ORD_GNO_BRNO": ord_gno_brno,
        "ODNO": odno,
        "INQR_DVSN_1": inqr_dvsn_1,
        "CTX_AREA_FK100": FK100,
        "CTX_AREA_NK100": NK100
    }

    if excg_id_dvsn_cd is not None:
        params["EXCG_ID_DVSN_CD"] = excg_id_dvsn_cd

    res = ka._url_fetch(api_url, tr_id, tr_cont, params)

    if res.isOK():
        # output1 (array) 처리
        current_data1 = pd.DataFrame(res.getBody().output1)
        if dataframe1 is not None:
            dataframe1 = pd.concat([dataframe1, current_data1], ignore_index=True)
        else:
            dataframe1 = current_data1

        # output2 (object) 처리
        current_data2 = pd.DataFrame([res.getBody().output2])
        if dataframe2 is not None:
            dataframe2 = pd.concat([dataframe2, current_data2], ignore_index=True)
        else:
            dataframe2 = current_data2

        tr_cont = res.getHeader().tr_cont
        FK100 = res.getBody().ctx_area_fk100
        NK100 = res.getBody().ctx_area_nk100

        if tr_cont in ["M", "F"]:  # 다음 페이지 존재
            logging.info("Call Next page...")
            ka.smart_sleep()  # 시스템 안정적 운영을 위한 지연
            return inquire_daily_ccld(
                env_dv, pd_dv, cano, acnt_prdt_cd, inqr_strt_dt, inqr_end_dt,
                sll_buy_dvsn_cd, pdno, ccld_dvsn, inqr_dvsn, inqr_dvsn_3,
                ord_gno_brno, odno, inqr_dvsn_1, FK100, NK100, "N",
                excg_id_dvsn_cd, dataframe1, dataframe2, depth + 1, max_depth
            )
        else:
            logging.info("Data fetch complete.")
            return dataframe1, dataframe2
    else:

exec
/bin/zsh -lc "sed -n '10205,10219p' examples_user/domestic_stock/domestic_stock_functions.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:

    res = ka._url_fetch(api_url, tr_id, "", params, postFlag=True)

    if res.isOK():
        current_data = pd.DataFrame([res.getBody().output])
        return current_data
    else:
        res.printError(url=api_url)
        return pd.DataFrame()


##############################################################################################
# [국내주식] 주문/계좌 > 주식주문(신용)[v1_국내주식-002]
##############################################################################################


exec
/bin/zsh -lc 'rg "def _url_fetch|headers|appkey|appsecret|custtype|hashkey|tr_id" -n . | head -200' in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
./MCP/MCP AI 도구 연결 방법.md:306:                kis_auth._base_headers["authorization"] = f"Bearer {saved_token}"
./examples_user/etfetn/etfetn_examples_ws.py:30:def on_result(ws, tr_id, result, data_info):
./examples_llm/etfetn/etf_nav_trend/chk_etf_nav_trend.py:64:    def on_result(ws, tr_id: str, result: pd.DataFrame, data_map: dict):
./examples_llm/etfetn/etf_nav_trend/etf_nav_trend.py:50:    tr_id = "H0STNAV0"
./examples_llm/etfetn/etf_nav_trend/etf_nav_trend.py:57:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_user/etfetn/etfetn_functions.py:56:    tr_id = "FHKST121600C0"
./examples_user/etfetn/etfetn_functions.py:70:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/etfetn/etfetn_functions.py:116:    tr_id = "FHPST02400000"  # ETF/ETN 현재가
./examples_user/etfetn/etfetn_functions.py:128:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/etfetn/etfetn_functions.py:179:    tr_id = "FHPST02440200"  # NAV 비교추이(일)
./examples_user/etfetn/etfetn_functions.py:193:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/etfetn/etfetn_functions.py:240:    tr_id = "FHPST02440100"
./examples_user/etfetn/etfetn_functions.py:253:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/etfetn/etfetn_functions.py:294:    tr_id = "FHPST02440000"  # NAV 비교추이(종목)
./examples_user/etfetn/etfetn_functions.py:306:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/etfetn/etfetn_functions_ws.py:46:    tr_id = "H0STNAV0"
./examples_user/etfetn/etfetn_functions_ws.py:53:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_llm/etfetn/nav_comparison_time_trend/nav_comparison_time_trend.py:57:    tr_id = "FHPST02440100"
./examples_llm/etfetn/nav_comparison_time_trend/nav_comparison_time_trend.py:65:    res = ka._url_fetch(API_URL, tr_id, "", params)
./MCP/KIS Code Assistant MCP/src/prompts/prompt.py:64:   - **WebSocket**: 1개 appkey당 최대 41건 등록 제한 (주석 또는 코드로 명시)
./MCP/KIS Code Assistant MCP/src/prompts/prompt.py:109:       # 주의: 1개 appkey당 최대 41건까지만 등록 가능
./MCP/KIS Code Assistant MCP/src/prompts/prompt.py:236:    # 주의: 1개 appkey당 최대 41건까지만 등록 가능
./MCP/KIS Code Assistant MCP/src/prompts/prompt.py:277:- **WebSocket**: 1개 appkey당 최대 41건 등록 제한 (주석 또는 코드로 명시)
./examples_llm/etfetn/inquire_price/inquire_price.py:50:    tr_id = "FHPST02400000"  # ETF/ETN 현재가
./examples_llm/etfetn/inquire_price/inquire_price.py:57:    res = ka._url_fetch(API_URL, tr_id, "", params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:93:    tr_id = "HHDFC55020100"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:111:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:227:    tr_id = "HHDFC86000000"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:238:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:372:    tr_id = "OTFM3116R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:389:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:524:    tr_id = "OTFM3122R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:545:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:704:    tr_id = "OTFM3120R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:724:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:826:    tr_id = "OTFM1411R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:840:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:963:    tr_id = "OTFM3118R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:982:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1132:    tr_id = "OTFM3114R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1151:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1232:    tr_id = "HHDFC55010000"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1243:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1343:    tr_id = "OTFM3304R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1359:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1475:    tr_id = "HHDFC55020400"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1493:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1647:    tr_id = "HHDFO55020100"  # 해외옵션 분봉조회
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1665:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1759:    tr_id = "OTFM1412R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1774:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1871:    tr_id = "HHDDB95030000"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:1885:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2010:    tr_id = "OTFM3115R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2024:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2120:    tr_id = "OTFM2229R"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2136:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2255:    tr_id = "HHDFC55020300"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2273:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2389:    tr_id = "HHDFO86000000"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2400:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2531:    tr_id = "HHDFO55020100"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2549:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2627:    tr_id = "HHDFO55010100"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2638:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2726:    tr_id = "HHDFO55020300"  # 해외옵션 체결추이(월간)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2744:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2816:    tr_id = "HHDFO55010000"  # 해외옵션종목현재가
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2827:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2923:    tr_id = "HHDFO55020200"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:2941:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3056:    tr_id = "HHDFO55020000"  # 해외옵션 체결추이(주간)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3074:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3202:    tr_id = "OTFM3001U"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3229:                        ptr_id=tr_id,
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3321:        tr_id = "OTFM3002U"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3323:        tr_id = "OTFM3003U"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3349:                         ptr_id=tr_id,
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3417:    tr_id = "HHDFC55200000"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3434:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3569:    tr_id = "HHDFO55200000"  # 해외옵션 상품기본정보
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3641:    res = ka._url_fetch(api_url, tr_id, "", params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3690:    tr_id = "HHDFC55010100"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3701:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3812:    tr_id = "HHDFC55020200"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3830:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3972:    tr_id = "HHDFC55020000"
./examples_user/overseas_futureoption/overseas_futureoption_functions.py:3990:    res = ka._url_fetch(api_url, tr_id, tr_cont, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:50:    tr_id = "HDFFF010"
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:56:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:133:    tr_id = "HDFFF020"
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:139:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:202:    tr_id = "HDFFF2C0"
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:208:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:280:    tr_id = "HDFFF1C0"
./examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:286:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_llm/etfetn/nav_comparison_trend/nav_comparison_trend.py:52:    tr_id = "FHPST02440000"  # NAV 비교추이(종목)
./examples_llm/etfetn/nav_comparison_trend/nav_comparison_trend.py:59:    res = ka._url_fetch(API_URL, tr_id, "", params)
./examples_user/overseas_futureoption/overseas_futureoption_examples_ws.py:48:def on_result(ws, tr_id, result, data_info):
./examples_user/kis_auth.py:60:_base_headers = {
./examples_user/kis_auth.py:106:    return copy.deepcopy(_base_headers)
./examples_user/kis_auth.py:208:    p["appkey"] = _cfg[ak1]
./examples_user/kis_auth.py:209:    p["appsecret"] = _cfg[ak2]
./examples_user/kis_auth.py:217:            url, data=json.dumps(p), headers=_getBaseHeader()
./examples_user/kis_auth.py:235:    _base_headers["authorization"] = f"Bearer {my_token}"
./examples_user/kis_auth.py:236:    _base_headers["appkey"] = _TRENV.my_app
./examples_user/kis_auth.py:237:    _base_headers["appsecret"] = _TRENV.my_sec
./examples_user/kis_auth.py:274:    url = f"{getTREnv().my_url}/uapi/hashkey"  # hashkey 발급 API URL
./examples_user/kis_auth.py:276:    res = requests.post(url, data=json.dumps(p), headers=h)
./examples_user/kis_auth.py:279:        h["hashkey"] = _getResultObject(res.json()).HASH
./examples_user/kis_auth.py:299:        for x in self._resp.headers.keys():
./examples_user/kis_auth.py:301:                fld[x] = self._resp.headers.get(x)
./examples_user/kis_auth.py:413:def _url_fetch(
./examples_user/kis_auth.py:414:        api_url, ptr_id, tr_cont, params, appendHeaders=None, postFlag=False, hashFlag=True
./examples_user/kis_auth.py:418:    headers = _getBaseHeader()  # 기본 header 값 정리
./examples_user/kis_auth.py:421:    tr_id = ptr_id
./examples_user/kis_auth.py:422:    if ptr_id[0] in ("T", "J", "C"):  # 실전투자용 TR id 체크
./examples_user/kis_auth.py:424:            tr_id = "V" + ptr_id[1:]
./examples_user/kis_auth.py:426:    headers["tr_id"] = tr_id  # 트랜젝션 TR id
./examples_user/kis_auth.py:427:    headers["custtype"] = "P"  # 일반(개인고객,법인고객) "P", 제휴사 "B"
./examples_user/kis_auth.py:428:    headers["tr_cont"] = tr_cont  # 트랜젝션 TR id
./examples_user/kis_auth.py:433:                headers[x] = appendHeaders.get(x)
./examples_user/kis_auth.py:437:        print(f"URL: {url}, TR: {tr_id}")
./examples_user/kis_auth.py:438:        print(f"<header>\n{headers}")
./examples_user/kis_auth.py:442:        # if (hashFlag): set_order_hash_key(headers, params)
./examples_user/kis_auth.py:443:        res = requests.post(url, headers=headers, data=json.dumps(params))
./examples_user/kis_auth.py:445:        res = requests.get(url, headers=headers, params=params)
./examples_user/kis_auth.py:463:_base_headers_ws = {
./examples_user/kis_auth.py:472:    return copy.deepcopy(_base_headers_ws)
./examples_user/kis_auth.py:484:    p["appkey"] = _cfg[ak1]
./examples_user/kis_auth.py:488:    res = requests.post(url, data=json.dumps(p), headers=_getBaseHeader())  # 토큰 발급
./examples_user/kis_auth.py:498:    _base_headers_ws["approval_key"] = approval_key
./examples_user/kis_auth.py:513:def data_fetch(tr_id, tr_type, params, appendHeaders=None) -> dict:
./examples_user/kis_auth.py:514:    headers = _getBaseHeader_ws()  # 기본 header 값 정리
./examples_user/kis_auth.py:516:    headers["tr_type"] = tr_type
./examples_user/kis_auth.py:517:    headers["custtype"] = "P"
./examples_user/kis_auth.py:522:                headers[x] = appendHeaders.get(x)
./examples_user/kis_auth.py:526:        print(f"TR: {tr_id}")
./examples_user/kis_auth.py:527:        print(f"<header>\n{headers}")
./examples_user/kis_auth.py:530:        "tr_id": tr_id,
./examples_user/kis_auth.py:534:    return {"header": headers, "body": {"input": inp}}
./examples_user/kis_auth.py:548:    tr_id = rdic["header"]["tr_id"]
./examples_user/kis_auth.py:549:    if tr_id != "PINGPONG":
./examples_user/kis_auth.py:561:        isPingPong = True if tr_id == "PINGPONG" else False
./examples_user/kis_auth.py:567:            "tr_id",
./examples_user/kis_auth.py:579:        "tr_id": tr_id,
./examples_user/kis_auth.py:627:        tr_id: str,
./examples_user/kis_auth.py:633:    if data_map.get(tr_id, None) is None:
./examples_user/kis_auth.py:634:        data_map[tr_id] = {"columns": [], "encrypt": False, "key": None, "iv": None}
./examples_user/kis_auth.py:637:        data_map[tr_id]["columns"] = columns
./examples_user/kis_auth.py:640:        data_map[tr_id]["encrypt"] = encrypt
./examples_user/kis_auth.py:643:        data_map[tr_id]["key"] = key
./examples_user/kis_auth.py:646:        data_map[tr_id]["iv"] = iv
./examples_user/kis_auth.py:677:                tr_id = d1[1]
./examples_user/kis_auth.py:679:                dm = data_map[tr_id]
./examples_user/kis_auth.py:693:                tr_id = rsp.tr_id
./examples_user/kis_auth.py:695:                    tr_id=rsp.tr_id, encrypt=rsp.encrypt, key=rsp.ekey, iv=rsp.iv
./examples_user/kis_auth.py:707:                self.on_result(ws, tr_id, df, data_map[tr_id])
./examples_user/kis_auth.py:746:        add_data_map(tr_id=msg["body"]["input"]["tr_id"], columns=columns)
./examples_user/auth/auth_functions.py:23:        appkey: str,
./examples_user/auth/auth_functions.py:24:        appsecret: str,
./examples_user/auth/auth_functions.py:32:        appkey (str): [필수] 앱키 (한국투자증권 홈페이지에서 발급받은 appkey)
./examples_user/auth/auth_functions.py:33:        appsecret (str): [필수] 앱시크릿키 (한국투자증권 홈페이지에서 발급받은 appsecret)
./examples_user/auth/auth_functions.py:42:        ...     appkey=trenv.my_app,
./examples_user/auth/auth_functions.py:43:        ...     appsecret=trenv.my_sec,
./examples_user/auth/auth_functions.py:54:    if not appkey:
./examples_user/auth/auth_functions.py:55:        logger.error("appkey is required. (한국투자증권 홈페이지에서 발급받은 appkey)")
./examples_user/auth/auth_functions.py:56:        raise ValueError("appkey is required. (한국투자증권 홈페이지에서 발급받은 appkey)")
./examples_user/auth/auth_functions.py:58:    if not appsecret:
./examples_user/auth/auth_functions.py:59:        logger.error("appsecret is required. (한국투자증권 홈페이지에서 발급받은 appsecret)")
./examples_user/auth/auth_functions.py:60:        raise ValueError("appsecret is required. (한국투자증권 홈페이지에서 발급받은 appsecret)")
./examples_user/auth/auth_functions.py:79:    headers = {
./examples_user/auth/auth_functions.py:88:        "appkey": appkey,
./examples_user/auth/auth_functions.py:89:        "appsecret": appsecret,
./examples_user/auth/auth_functions.py:94:        response = requests.post(url, data=json.dumps(data), headers=headers)
./examples_user/auth/auth_functions.py:120:        appkey: str,
./examples_user/auth/auth_functions.py:121:        appsecret: str,
./examples_user/auth/auth_functions.py:130:        appkey (str): [필수] 고객 앱Key (한국투자증권 홈페이지에서 발급받은 appkey)
./examples_user/auth/auth_functions.py:131:        appsecret (str): [필수] 고객 앱Secret (한국투자증권 홈페이지에서 발급받은 appsecret)
./examples_user/auth/auth_functions.py:141:        ...     appkey=trenv.my_app,
./examples_user/auth/auth_functions.py:142:        ...     appsecret=trenv.my_sec,
./examples_user/auth/auth_functions.py:153:    if not appkey:
./examples_user/auth/auth_functions.py:154:        logger.error("appkey is required. (한국투자증권 홈페이지에서 발급받은 appkey)")
./examples_user/auth/auth_functions.py:155:        raise ValueError("appkey is required. (한국투자증권 홈페이지에서 발급받은 appkey)")
./examples_user/auth/auth_functions.py:157:    if not appsecret:
./examples_user/auth/auth_functions.py:158:        logger.error("appsecret is required. (한국투자증권 홈페이지에서 발급받은 appsecret)")
./examples_user/auth/auth_functions.py:159:        raise ValueError("appsecret is required. (한국투자증권 홈페이지에서 발급받은 appsecret)")
./examples_user/auth/auth_functions.py:178:    headers = {
./examples_user/auth/auth_functions.py:187:        "appkey": appkey,
./examples_user/auth/auth_functions.py:188:        "secretkey": appsecret,
./examples_user/auth/auth_functions.py:197:        response = requests.post(url, data=json.dumps(data), headers=headers)
./examples_llm/etfetn/nav_comparison_daily_trend/nav_comparison_daily_trend.py:62:    tr_id = "FHPST02440200"  # NAV 비교추이(일)
./examples_llm/etfetn/nav_comparison_daily_trend/nav_comparison_daily_trend.py:71:    res = ka._url_fetch(API_URL, tr_id, "", params)
./examples_user/domestic_stock/domestic_stock_functions_ws.py:51:        tr_id = "H0STASP0"  # 실전투자용 TR ID
./examples_user/domestic_stock/domestic_stock_functions_ws.py:53:        tr_id = "H0STASP0"  # 모의투자용 TR ID (웹소켓은 동일한 TR ID 사용)
./examples_user/domestic_stock/domestic_stock_functions_ws.py:62:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_user/domestic_stock/domestic_stock_functions_ws.py:118:    tr_id = "H0NXASP0"
./examples_user/domestic_stock/domestic_stock_functions_ws.py:125:    msg = ka.data_fetch(tr_id, tr_type, params)
./examples_user/domestic_stock/domestic_stock_functions_ws.py:233:    tr_id = "H0UNASP0"
./examples_user/domestic_stock/domestic_stock_functions_ws.py:240:    msg = ka.data_fetch(tr_id, tr_type, params)

codex
The order endpoints are confirmed as POST body APIs, and the sample wrapper does not currently add a `hashkey` even though KIS commonly documents it for order POSTs. I’ll note that distinction explicitly in the headers section.
exec
/bin/zsh -lc "sed -n '50,75p' examples_user/kis_auth.py && sed -n '413,446p' examples_user/kis_auth.py && sed -n '267,282p' examples_user/kis_auth.py" in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
    _cfg = yaml.load(f, Loader=yaml.FullLoader)

_TRENV = tuple()
_last_auth_time = datetime.now()
_autoReAuth = False
_DEBUG = False
_isPaper = False
_smartSleep = 0.1

# 기본 헤더값 정의
_base_headers = {
    "Content-Type": "application/json",
    "Accept": "text/plain",
    "charset": "UTF-8",
    "User-Agent": _cfg["my_agent"],
}


# 토큰 발급 받아 저장 (토큰값, 토큰 유효시간,1일, 6시간 이내 발급신청시는 기존 토큰값과 동일, 발급시 알림톡 발송)
def save_token(my_token, my_expired):
    # print(type(my_expired), my_expired)
    valid_date = datetime.strptime(my_expired, "%Y-%m-%d %H:%M:%S")
    # print('Save token date: ', valid_date)
    with open(token_tmp, "w", encoding="utf-8") as f:
        f.write(f"token: {my_token}\n")
        f.write(f"valid-date: {valid_date}\n")
def _url_fetch(
        api_url, ptr_id, tr_cont, params, appendHeaders=None, postFlag=False, hashFlag=True
):
    url = f"{getTREnv().my_url}{api_url}"

    headers = _getBaseHeader()  # 기본 header 값 정리

    # 추가 Header 설정
    tr_id = ptr_id
    if ptr_id[0] in ("T", "J", "C"):  # 실전투자용 TR id 체크
        if isPaperTrading():  # 모의투자용 TR id 식별
            tr_id = "V" + ptr_id[1:]

    headers["tr_id"] = tr_id  # 트랜젝션 TR id
    headers["custtype"] = "P"  # 일반(개인고객,법인고객) "P", 제휴사 "B"
    headers["tr_cont"] = tr_cont  # 트랜젝션 TR id

    if appendHeaders is not None:
        if len(appendHeaders) > 0:
            for x in appendHeaders.keys():
                headers[x] = appendHeaders.get(x)

    if _DEBUG:
        print("< Sending Info >")
        print(f"URL: {url}, TR: {tr_id}")
        print(f"<header>\n{headers}")
        print(f"<body>\n{params}")

    if postFlag:
        # if (hashFlag): set_order_hash_key(headers, params)
        res = requests.post(url, headers=headers, data=json.dumps(params))
    else:
        res = requests.get(url, headers=headers, params=params)



# 주문 API에서 사용할 hash key값을 받아 header에 설정해 주는 함수
# 현재는 hash key 필수 사항아님, 생략가능, API 호출과정에서 변조 우려를 하는 경우 사용
# Input: HTTP Header, HTTP post param
# Output: None
def set_order_hash_key(h, p):
    url = f"{getTREnv().my_url}/uapi/hashkey"  # hashkey 발급 API URL

    res = requests.post(url, data=json.dumps(p), headers=h)
    rescode = res.status_code
    if rescode == 200:
        h["hashkey"] = _getResultObject(res.json()).HASH
    else:
        print("Error:", rescode)


exec
/bin/zsh -lc 'rg "hashkey|HASH|order-cash|order" docs README.md examples_user -n | head -120' in /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.xYaNMmhzkw/open-trading-api
 succeeded in 0ms:
examples_user/kis_auth.py:273:def set_order_hash_key(h, p):
examples_user/kis_auth.py:274:    url = f"{getTREnv().my_url}/uapi/hashkey"  # hashkey 발급 API URL
examples_user/kis_auth.py:279:        h["hashkey"] = _getResultObject(res.json()).HASH
examples_user/kis_auth.py:442:        # if (hashFlag): set_order_hash_key(headers, params)
examples_user/domestic_futureoption/domestic_futureoption_examples.py:205:result = inquire_psbl_ngt_order(
examples_user/domestic_futureoption/domestic_futureoption_examples.py:220:result = inquire_psbl_order(
examples_user/domestic_futureoption/domestic_futureoption_examples.py:260:result = order(
examples_user/domestic_futureoption/domestic_futureoption_examples.py:280:result = order_rvsecncl(
examples_user/domestic_bond/domestic_bond_examples.py:100:df = inquire_psbl_order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="KR2033022D33", bond_ord_unpr="1000")
examples_user/domestic_bond/domestic_bond_examples.py:121:result = order_rvsecncl(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:621:def inquire_daily_order(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:662:        >>> df = inquire_daily_order(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:707:    api_url = "/uapi/overseas-futureoption/v1/trading/inquire-daily-order"
examples_user/overseas_futureoption/overseas_futureoption_functions.py:745:            return inquire_daily_order(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3113:def order(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3159:        >>> df = order(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3205:    api_url = "/uapi/overseas-futureoption/v1/trading/order"
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3255:def order_rvsecncl(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3291:        >>> df = order_rvsecncl(
examples_user/overseas_futureoption/overseas_futureoption_functions.py:3329:    api_url = "/uapi/overseas-futureoption/v1/trading/order-rvsecncl"
examples_user/domestic_stock/domestic_stock_examples.py:640:result = inquire_psbl_order(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930",
examples_user/domestic_stock/domestic_stock_examples.py:949:result = order_cash(env_dv="real", ord_dv="sell", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930",
examples_user/domestic_stock/domestic_stock_examples.py:957:result = order_credit(
examples_user/domestic_stock/domestic_stock_examples.py:974:result = order_resv(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_qty="1", ord_unpr="55000",
examples_user/domestic_stock/domestic_stock_examples.py:982:result = order_resv_ccnl(
examples_user/domestic_stock/domestic_stock_examples.py:997:result = order_resv_rvsecncl(
examples_user/domestic_stock/domestic_stock_examples.py:1017:result = order_rvsecncl(
examples_user/domestic_stock/domestic_stock_examples.py:1116:result = pension_inquire_psbl_order(
examples_user/overseas_stock/overseas_stock_examples.py:29:df = daytime_order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, order_dv="buy", ovrs_excg_cd="NASD", pdno="AAPL",
examples_user/overseas_stock/overseas_stock_examples.py:38:df = daytime_order_rvsecncl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", pdno="AAPL",
examples_user/overseas_stock/overseas_stock_examples.py:150:df = order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", pdno="AAPL", ord_qty="10",
examples_user/overseas_stock/overseas_stock_examples.py:159:result = order_resv(env_dv="real", ord_dv="usBuy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod,
examples_user/overseas_stock/overseas_stock_examples.py:167:result = order_resv_ccnl(
examples_user/overseas_stock/overseas_stock_examples.py:181:df = order_resv_list(nat_dv="us", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_strt_dt="20220809",
examples_user/overseas_stock/overseas_stock_examples.py:189:df = order_rvsecncl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NYSE", pdno="BA",
examples_user/overseas_futureoption/overseas_futureoption_examples.py:53:df = inquire_daily_order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, strt_dt="20250601", end_dt="20250703", fm_pdgr_cd="", ccld_nccs_dvsn="01", sll_buy_dvsn_cd="%%", fuop_dvsn="00", ctx_area_fk200="", ctx_area_nk200="")
examples_user/overseas_futureoption/overseas_futureoption_examples.py:204:df = order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_futr_fx_pdno="1AALN25 C10.0", sll_buy_dvsn_cd="02", fm_lqd_ustl_ccld_dt="", fm_lqd_ustl_ccno="", pric_dvsn_cd="1", fm_limit_ord_pric="1.17", fm_stop_ord_pric="", fm_ord_qty="1", fm_lqd_lmt_ord_pric="", fm_lqd_stop_ord_pric="", ccld_cndt_cd="6", cplx_ord_dvsn_cd="0", ecis_rsvn_ord_yn="N", fm_hdge_ord_scrn_yn="N")
examples_user/overseas_futureoption/overseas_futureoption_examples.py:211:df = order_rvsecncl(cano=trenv.my_acct, ord_dv="0", acnt_prdt_cd=trenv.my_prod, orgn_ord_dt="20250630", orgn_odno="00123456", fm_limit_ord_pric="10.0", fm_stop_ord_pric="", fm_lqd_lmt_ord_pric="", fm_lqd_stop_ord_pric="", fm_hdge_ord_scrn_yn="N", fm_mkpr_cvsn_yn="")
examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:251:def order_notice(
examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py:269:        >>> msg, columns = order_notice("1", trenv.my_htsid)
examples_user/overseas_futureoption/overseas_futureoption_examples_ws.py:44:kws.subscribe(request=order_notice, data=[trenv.my_htsid])
examples_user/domestic_bond/domestic_bond_functions.py:1059:def inquire_psbl_order(
examples_user/domestic_bond/domestic_bond_functions.py:1088:        >>> df = inquire_psbl_order("12345678", "01", "KR2033022D33", "1000")
examples_user/domestic_bond/domestic_bond_functions.py:1116:    api_url = "/uapi/domestic-bond/v1/trading/inquire-psbl-order"
examples_user/domestic_bond/domestic_bond_functions.py:1152:            return inquire_psbl_order(
examples_user/domestic_bond/domestic_bond_functions.py:1390:def order_rvsecncl(
examples_user/domestic_bond/domestic_bond_functions.py:1425:        >>> df = order_rvsecncl(
examples_user/domestic_bond/domestic_bond_functions.py:1440:    api_url = "/uapi/domestic-bond/v1/trading/order-rvsecncl"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1615:def inquire_psbl_ngt_order(
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1640:        >>> df = inquire_psbl_ngt_order(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="101W09", prdt_type_cd="301", sll_buy_dvsn_cd="02", unit_price="322", ord_dvsn_cd="01")
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1669:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-psbl-ngt-order"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1696:def inquire_psbl_order(
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1721:        >>> df = inquire_psbl_order(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod,
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1757:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-psbl-order"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1934:def order(
examples_user/domestic_futureoption/domestic_futureoption_functions.py:1981:        >>> df = order(env_dv="real", ord_dv="day", ord_prcs_dvsn_cd="02", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, sll_buy_dvsn_cd="02", shtn_pdno="101W09", ord_qty="1", unit_price="0", nmpr_type_cd="02", krx_nmpr_cndt_cd="0", ord_dvsn_cd="02")
examples_user/domestic_futureoption/domestic_futureoption_functions.py:2039:    api_url = "/uapi/domestic-futureoption/v1/trading/order"
examples_user/domestic_futureoption/domestic_futureoption_functions.py:2070:def order_rvsecncl(
examples_user/domestic_futureoption/domestic_futureoption_functions.py:2112:        >>> df = order_rvsecncl(
examples_user/domestic_futureoption/domestic_futureoption_functions.py:2139:    api_url = "/uapi/domestic-futureoption/v1/trading/order-rvsecncl"
examples_user/domestic_futureoption/domestic_futureoption_functions_ws.py:252:        "order_prc"
examples_user/overseas_stock/overseas_stock_functions.py:113:def daytime_order(
examples_user/overseas_stock/overseas_stock_functions.py:114:        order_dv: str,  # 주문구분 buy(매수) / sell(매도)
examples_user/overseas_stock/overseas_stock_functions.py:133:        order_dv (str): 주문구분 buy(매수) / sell(매도)
examples_user/overseas_stock/overseas_stock_functions.py:149:        >>> df = daytime_order(
examples_user/overseas_stock/overseas_stock_functions.py:150:        ...     order_dv="buy",
examples_user/overseas_stock/overseas_stock_functions.py:190:    if order_dv == "buy":
examples_user/overseas_stock/overseas_stock_functions.py:192:    elif order_dv == "sell":
examples_user/overseas_stock/overseas_stock_functions.py:195:        logger.error("Invalid order_dv. (e.g. 'buy' or 'sell')")
examples_user/overseas_stock/overseas_stock_functions.py:196:        raise ValueError("Invalid order_dv. (e.g. 'buy' or 'sell')")
examples_user/overseas_stock/overseas_stock_functions.py:198:    api_url = "/uapi/overseas-stock/v1/trading/daytime-order"
examples_user/overseas_stock/overseas_stock_functions.py:240:def daytime_order_rvsecncl(
examples_user/overseas_stock/overseas_stock_functions.py:276:        >>> df = daytime_order_rvsecncl(
examples_user/overseas_stock/overseas_stock_functions.py:322:    api_url = "/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl"
examples_user/overseas_stock/overseas_stock_functions.py:2137:def order(
examples_user/overseas_stock/overseas_stock_functions.py:2175:        >>> df = order(
examples_user/overseas_stock/overseas_stock_functions.py:2270:    api_url = "/uapi/overseas-stock/v1/trading/order"
examples_user/overseas_stock/overseas_stock_functions.py:2314:def order_resv(
examples_user/overseas_stock/overseas_stock_functions.py:2399:        >>> df = order_resv(env_dv="real", ord_dv="usBuy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="TSLA", ovrs_excg_cd="NASD", ft_ord_qty="1", ft_ord_unpr3="900")
examples_user/overseas_stock/overseas_stock_functions.py:2450:    api_url = "/uapi/overseas-stock/v1/trading/order-resv"
examples_user/overseas_stock/overseas_stock_functions.py:2494:def order_resv_ccnl(
examples_user/overseas_stock/overseas_stock_functions.py:2524:        >>> df = order_resv_ccnl(env_dv="real", nat_dv="us", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, rsvn_ord_rcit_dt="20220810", ovrs_rsvn_odno="0030008244")
examples_user/overseas_stock/overseas_stock_functions.py:2560:    api_url = "/uapi/overseas-stock/v1/trading/order-resv-ccnl"
examples_user/overseas_stock/overseas_stock_functions.py:2585:def order_resv_list(
examples_user/overseas_stock/overseas_stock_functions.py:2628:        >>> df = order_resv_list(nat_dv="us", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, inqr_strt_dt="20250101", inqr_end_dt="20251231", inqr_dvsn_cd="00", ovrs_excg_cd="NASD")
examples_user/overseas_stock/overseas_stock_functions.py:2668:    api_url = "/uapi/overseas-stock/v1/trading/order-resv-list"
examples_user/overseas_stock/overseas_stock_functions.py:2699:            return order_resv_list(
examples_user/overseas_stock/overseas_stock_functions.py:2716:def order_rvsecncl(
examples_user/overseas_stock/overseas_stock_functions.py:2752:        >>> df = order_rvsecncl(
examples_user/overseas_stock/overseas_stock_functions.py:2801:    api_url = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
examples_user/domestic_stock/domestic_stock_functions.py:6206:def inquire_psbl_order(
examples_user/domestic_stock/domestic_stock_functions.py:6247:        >>> df = inquire_psbl_order(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_unpr="55000", ord_dvsn="01", cma_evlu_amt_icld_yn="N", ovrs_icld_yn="N")
examples_user/domestic_stock/domestic_stock_functions.py:6250:    api_url = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"
examples_user/domestic_stock/domestic_stock_functions.py:10097:def order_cash(
examples_user/domestic_stock/domestic_stock_functions.py:10143:        >>> df = order_cash(env_dv="demo", ord_dv="buy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_dvsn="00", ord_qty="1", ord_unpr="70000", excg_id_dvsn_cd="KRX")
examples_user/domestic_stock/domestic_stock_functions.py:10146:    api_url = "/uapi/domestic-stock/v1/trading/order-cash"
examples_user/domestic_stock/domestic_stock_functions.py:10220:def order_credit(
examples_user/domestic_stock/domestic_stock_functions.py:10285:        >>> df = order_credit(ord_dv="buy", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", crdt_type="21", loan_dt="20220810", ord_dvsn="00", ord_qty="1", ord_unpr="55000")
examples_user/domestic_stock/domestic_stock_functions.py:10288:    api_url = "/uapi/domestic-stock/v1/trading/order-credit"
examples_user/domestic_stock/domestic_stock_functions.py:10387:def order_resv(
examples_user/domestic_stock/domestic_stock_functions.py:10452:        >>> df = order_resv(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, pdno="005930", ord_qty="1", ord_unpr="55000", sll_buy_dvsn_cd="02", ord_dvsn_cd="00", ord_objt_cblc_dvsn_cd="10")
examples_user/domestic_stock/domestic_stock_functions.py:10455:    api_url = "/uapi/domestic-stock/v1/trading/order-resv"
examples_user/domestic_stock/domestic_stock_functions.py:10515:def order_resv_ccnl(
examples_user/domestic_stock/domestic_stock_functions.py:10559:        >>> df = order_resv_ccnl(
examples_user/domestic_stock/domestic_stock_functions.py:10569:    api_url = "/uapi/domestic-stock/v1/trading/order-resv-ccnl"
examples_user/domestic_stock/domestic_stock_functions.py:10634:            return order_resv_ccnl(
examples_user/domestic_stock/domestic_stock_functions.py:10651:def order_resv_rvsecncl(
examples_user/domestic_stock/domestic_stock_functions.py:10697:        >>> df = order_resv_rvsecncl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, rsvn_ord_seq="88793", rsvn_ord_orgno="123", rsvn_ord_ord_dt="20250113", ord_type="cancel")
examples_user/domestic_stock/domestic_stock_functions.py:10700:    api_url = "/uapi/domestic-stock/v1/trading/order-resv-rvsecncl"
examples_user/domestic_stock/domestic_stock_functions.py:10771:def order_rvsecncl(
examples_user/domestic_stock/domestic_stock_functions.py:10813:        >>> df = order_rvsecncl(env_dv="real", cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ...)
examples_user/domestic_stock/domestic_stock_functions.py:10816:    api_url = "/uapi/domestic-stock/v1/trading/order-rvsecncl"
examples_user/domestic_stock/domestic_stock_functions.py:11679:def pension_inquire_psbl_order(
examples_user/domestic_stock/domestic_stock_functions.py:11707:        >>> df = pension_inquire_psbl_order(
examples_user/domestic_stock/domestic_stock_functions.py:11717:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-psbl-order"

web search: 
web search: https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/overseas_stock/overseas_stock_functions.py
web search: 
web search: https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/overseas_stock/overseas_stock_functions.py
codex
Verified against the official KIS `open-trading-api` samples and KIS API portal pages. Base URL for paper: `https://openapivts.koreainvestment.com:29443`.

| # | Call | Method + path | PAPER `tr_id` | Key params/body |
|---|---|---|---|---|
| 1 | Overseas US/NASDAQ daily OHLCV, `해외주식 기간별시세` | `GET /uapi/overseas-price/v1/quotations/dailyprice` | `HHDFS76240000` | Query: `AUTH=""`, `EXCD="NAS"` for NASDAQ price inquiry, `SYMB="AAPL"`, `GUBN="0"` daily, `BYMD="YYYYMMDD"` 기준일, `MODP="0"`/`"1"` 수정주가 여부. Note: quote TR is same for real/paper, not `V...`. |
| 2 | Domestic KOSPI/KRX historical daily OHLCV, `국내주식기간별시세(일/주/월/년)` | `GET /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice` | `FHKST03010100` | Query: `FID_COND_MRKT_DIV_CODE="J"` for KRX, `FID_INPUT_ISCD="005930"`, `FID_INPUT_DATE_1="YYYYMMDD"`, `FID_INPUT_DATE_2="YYYYMMDD"`, `FID_PERIOD_DIV_CODE="D"`, `FID_ORG_ADJ_PRC="0"` 수정주가 / `"1"` 원주가 per sample. Quote TR is same for paper. |
| 3 | Overseas US stock order, paper | `POST /uapi/overseas-stock/v1/trading/order` | Buy: `VTTT1002U`; Sell: `VTTT1006U` | JSON body: `CANO`, `ACNT_PRDT_CD`, `OVRS_EXCG_CD="NASD"` for NASDAQ orders, `PDNO="AAPL"`, `ORD_QTY`, `OVRS_ORD_UNPR` (`"0"` for market-style where accepted; paper US sample notes only `ORD_DVSN="00"` limit is supported), `ORD_DVSN="00"`, `ORD_SVR_DVSN_CD="0"`, `CTAC_TLNO=""`, `MGCO_APTM_ODNO=""`, `SLL_TYPE=""` for buy / `"00"` for sell. |
| 4 | Domestic stock cash order, paper | `POST /uapi/domestic-stock/v1/trading/order-cash` | Buy: `VTTC0012U`; Sell: `VTTC0011U` | JSON body: `CANO`, `ACNT_PRDT_CD`, `PDNO="005930"`, `ORD_DVSN`, `ORD_QTY`, `ORD_UNPR`, `EXCG_ID_DVSN_CD="KRX"`; optional `SLL_TYPE` for sell, `CNDT_PRIC`. |
| 5a | Overseas order/fill inquiry, paper, `해외주식 주문체결내역` | `GET /uapi/overseas-stock/v1/trading/inquire-ccnl` | `VTTS3035R` | Query: `CANO`, `ACNT_PRDT_CD`, `PDNO` (`""` for all in paper per sample), `ORD_STRT_DT`, `ORD_END_DT`, `SLL_BUY_DVSN="00"` paper all only, `CCLD_NCCS_DVSN="00"` paper all only, `OVRS_EXCG_CD=""` paper all only, `SORT_SQN="DS"`, `ORD_DT=""`, `ORD_GNO_BRNO=""`, `ODNO=""`, `CTX_AREA_NK200=""`, `CTX_AREA_FK200=""`. |
| 5b | Domestic order/fill inquiry, paper, `주식일별주문체결조회` | `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld` | Within 3 months: `VTTC0081R`; older than 3 months: `VTSC9215R` | Query: `CANO`, `ACNT_PRDT_CD`, `INQR_STRT_DT`, `INQR_END_DT`, `SLL_BUY_DVSN_CD="00"` all / `"01"` sell / `"02"` buy, `PDNO`, `CCLD_DVSN="00"` all / `"01"` filled / `"02"` unfilled, `INQR_DVSN="00"` reverse / `"01"` normal, `INQR_DVSN_3="00"`, `EXCG_ID_DVSN_CD="KRX"` or `ALL`, `CTX_AREA_FK100=""`, `CTX_AREA_NK100=""`. |

Common REST headers:

```http
Content-Type: application/json
Accept: text/plain
charset: UTF-8
authorization: Bearer {access_token}
appkey: {paper_app_key}
appsecret: {paper_app_secret}
tr_id: {TR_ID}
custtype: P
tr_cont: ""        # or "N" for next-page continuation
```

For POST order calls, body keys must be uppercase. KIS samples state `hashkey` via `POST /uapi/hashkey` is currently optional, not mandatory; use it if you want tamper-checking on order bodies.

Sources: official KIS sample repo pages for [overseas stock functions](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/overseas_stock/overseas_stock_functions.py), [domestic stock functions](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/domestic_stock/domestic_stock_functions.py), and [auth/header handling](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/kis_auth.py); KIS API portal page for domestic daily price shown in search result.
tokens used
169,939

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
