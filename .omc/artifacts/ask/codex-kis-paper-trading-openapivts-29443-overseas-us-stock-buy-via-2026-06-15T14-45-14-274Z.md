# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-15T14:45:14.275Z

## Original task

KIS (한국투자증권) PAPER trading (모의투자, openapivts...:29443). Overseas US stock BUY via POST /uapi/overseas-stock/v1/trading/order with tr_id VTTT1002U WORKED and FILLED (rt_cd 0). But SELL with tr_id VTTT1006U returns rt_cd=1 msg '모의투자에서는 해당업무가 제공되지 않습니다' (this service not provided in paper trading). I have 1 share AAPL held in the paper account and need to sell it.

Questions, precise:
1. What is the CORRECT overseas-stock US SELL tr_id for PAPER (모의투자)? Is it VTTT1006U, VTTT1001U, or something else? List the known US (NASD/NASDAQ) paper order tr_ids for buy and sell. Cross-check: is VTTT1006U maybe a real-trading or different-exchange id?
2. Does KIS overseas PAPER trading actually SUPPORT sell orders, or is it genuinely restricted (some KIS paper features are disabled)? If overseas paper sell is unsupported, how do people flatten/test sells in paper? 
3. If a different tr_id or field (e.g. SLL_TYPE, or a different ORD_DVSN) is needed for the sell to be accepted in paper, give the exact body.
4. Is the order endpoint path the same for sell (/uapi/overseas-stock/v1/trading/order)?
Cite KIS sample/portal if known. Be precise and terse — I need the working sell call.

## Final prompt

KIS (한국투자증권) PAPER trading (모의투자, openapivts...:29443). Overseas US stock BUY via POST /uapi/overseas-stock/v1/trading/order with tr_id VTTT1002U WORKED and FILLED (rt_cd 0). But SELL with tr_id VTTT1006U returns rt_cd=1 msg '모의투자에서는 해당업무가 제공되지 않습니다' (this service not provided in paper trading). I have 1 share AAPL held in the paper account and need to sell it.

Questions, precise:
1. What is the CORRECT overseas-stock US SELL tr_id for PAPER (모의투자)? Is it VTTT1006U, VTTT1001U, or something else? List the known US (NASD/NASDAQ) paper order tr_ids for buy and sell. Cross-check: is VTTT1006U maybe a real-trading or different-exchange id?
2. Does KIS overseas PAPER trading actually SUPPORT sell orders, or is it genuinely restricted (some KIS paper features are disabled)? If overseas paper sell is unsupported, how do people flatten/test sells in paper? 
3. If a different tr_id or field (e.g. SLL_TYPE, or a different ORD_DVSN) is needed for the sell to be accepted in paper, give the exact body.
4. Is the order endpoint path the same for sell (/uapi/overseas-stock/v1/trading/order)?
Cite KIS sample/portal if known. Be precise and terse — I need the working sell call.

## Raw output

```text
Correct working call for KIS overseas **paper US sell** is:

`tr_id: VTTT1001U`

not `VTTT1006U`.

Known US order `tr_id`s:

| Use | Real | Paper |
|---|---:|---:|
| US buy | `TTTT1002U` | `VTTT1002U` |
| US sell | `TTTT1006U` | `VTTT1001U` |
| US revise/cancel | `TTTT1004U` | `VTTT1004U` |
| US reserve buy | `TTTT3014U` | `VTTT3014U` |
| US reserve sell | `TTTT3016U` | `VTTT3016U` |

`VTTT1006U` is the misleading one: newer KIS Python sample derives it by prefixing real US sell `TTTT1006U` with `V`, but the official KIS Postman sample lists paper US sell as `VTTT1001U`; your error confirms `VTTT1006U` is not accepted in VTS paper for this job. KIS sample repo: [Python sample shows the bad derivation](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/order/order.py), while [official Postman sample lists `VTTT1001U`](https://github.com/koreainvestment/open-trading-api/blob/main/legacy/postman/%EB%AA%A8%EC%9D%98%EA%B3%84%EC%A2%8C_POSTMAN_%EC%83%98%ED%94%8C%EC%BD%94%EB%93%9C_v1.6.json). A separate summary of KIS API ids also lists paper US sell as `VTTT1001U` and paper US buy as `VTTT1002U`.

Use the same endpoint:

`POST https://openapivts.koreainvestment.com:29443/uapi/overseas-stock/v1/trading/order`

Headers:

```http
content-type: application/json
authorization: Bearer {ACCESS_TOKEN}
appkey: {PAPER_APPKEY}
appsecret: {PAPER_APPSECRET}
tr_id: VTTT1001U
custtype: P
```

Body for selling 1 AAPL limit:

```json
{
  "CANO": "12345678",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "NASD",
  "PDNO": "AAPL",
  "ORD_QTY": "1",
  "OVRS_ORD_UNPR": "195.00",
  "SLL_TYPE": "00",
  "ORD_SVR_DVSN_CD": "0",
  "ORD_DVSN": "00"
}
```

For paper US, use `ORD_DVSN: "00"` limit. Do not use US daytime order for paper; KIS lists daytime overseas stock paper trading as unsupported. To flatten in paper, submit normal-session sell with `VTTT1001U`, or after hours place a reserve sell with `VTTT3016U` on `/uapi/overseas-stock/v1/trading/order-resv`.


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ecbbc-ca73-7a32-a58e-137f5bc9f513
--------
user
KIS (한국투자증권) PAPER trading (모의투자, openapivts...:29443). Overseas US stock BUY via POST /uapi/overseas-stock/v1/trading/order with tr_id VTTT1002U WORKED and FILLED (rt_cd 0). But SELL with tr_id VTTT1006U returns rt_cd=1 msg '모의투자에서는 해당업무가 제공되지 않습니다' (this service not provided in paper trading). I have 1 share AAPL held in the paper account and need to sell it.

Questions, precise:
1. What is the CORRECT overseas-stock US SELL tr_id for PAPER (모의투자)? Is it VTTT1006U, VTTT1001U, or something else? List the known US (NASD/NASDAQ) paper order tr_ids for buy and sell. Cross-check: is VTTT1006U maybe a real-trading or different-exchange id?
2. Does KIS overseas PAPER trading actually SUPPORT sell orders, or is it genuinely restricted (some KIS paper features are disabled)? If overseas paper sell is unsupported, how do people flatten/test sells in paper? 
3. If a different tr_id or field (e.g. SLL_TYPE, or a different ORD_DVSN) is needed for the sell to be accepted in paper, give the exact body.
4. Is the order endpoint path the same for sell (/uapi/overseas-stock/v1/trading/order)?
Cite KIS sample/portal if known. Be precise and terse — I need the working sell call.
codex
I’ll verify this against KIS’s current portal/sample material rather than guessing from memory, because their paper and real `tr_id` sets differ and the error you got is exactly the kind of mismatch their docs can make hard to spot.
web search: 
web search: KIS openapivts overseas stock order VTTT1006U sell tr_id
web search: 
web search: https://github.com/koreainvestment/open-trading-api
codex
The official sample repo is available and explicitly says separate real/paper app keys and `svr="vps"` for paper. I’m drilling into the overseas stock order examples now to pin down the exact `tr_id` mapping.
exec
/bin/zsh -lc 'rg -n "VTTT100|TTTT100|JTTT100|overseas.*order|SLL_TYPE|ORD_DVSN" . || true' in /Users/manager/side/makemoney
 succeeded in 0ms:
./docs/kis-api-reference.md:29:| 해외 주문 | `POST /uapi/overseas-stock/v1/trading/order` | 매수 `VTTT1002U` / 매도 `VTTT1006U` | ✅ rt_cd=1 msg1="모의투자 장시작전 입니다." (장마감 시간대 — 인증/TR_ID/body 정상 수락, 비즈니스 오류) |
./docs/kis-api-reference.md:41:- **해외 주문 body**(대문자): `CANO`, `ACNT_PRDT_CD`, `OVRS_EXCG_CD="NASD"`, `PDNO`, `ORD_QTY`, `OVRS_ORD_UNPR`, `ORD_DVSN="00"`(지정가; 모의 US는 지정가만 지원 가능성), `ORD_SVR_DVSN_CD="0"`.
./docs/kis-api-reference.md:42:- **국내 주문 body**: `CANO`, `ACNT_PRDT_CD`, `PDNO`, `ORD_DVSN`(00 지정가/01 시장가), `ORD_QTY`, `ORD_UNPR`, `EXCG_ID_DVSN_CD="KRX"`.
./docs/kis-api-reference.md:48:- 해외 주문 (`VTTT1002U`): 라이브 검증 완료 — rt_cd=1 "모의투자 장시작전 입니다." (장마감 시간대 비즈니스 오류. 인증/TR_ID/path/body 정상 수락 확인.)
./docs/superpowers/plans/2026-06-15-phase1-trading-engine.md:1481:        path = "/overseas/order" if market == "NASDAQ" else "/domestic/order"  # 실제 KIS 경로로 교체
./tests/test_kis_orders.py:38:# Test (a): NASDAQ BUY — overseas order path, correct tr_id and body, returns ODNO
./tests/test_kis_orders.py:41:def test_nasdaq_buy_posts_overseas_order_and_returns_odno(tmp_path):
./tests/test_kis_orders.py:48:        if p.endswith("/uapi/overseas-stock/v1/trading/order"):
./tests/test_kis_orders.py:66:    assert captured["tr_id"] == "VTTT1002U"
./tests/test_kis_orders.py:67:    assert captured["path"] == "/uapi/overseas-stock/v1/trading/order"
./tests/test_kis_orders.py:76:    assert body["ORD_DVSN"] == "00"
./tests/test_kis_orders.py:87:        if p.endswith("/uapi/overseas-stock/v1/trading/order"):
./tests/test_kis_orders.py:98:    assert captured["tr_id"] == "VTTT1006U"
./trader/execution/kis_client.py:506:            order_type: KIS ORD_DVSN code — "00" limit / "01" market.
./trader/execution/kis_client.py:517:            tr_id = "VTTT1002U" if side == "BUY" else "VTTT1006U"
./trader/execution/kis_client.py:518:            path = "/uapi/overseas-stock/v1/trading/order"
./trader/execution/kis_client.py:526:                "ORD_DVSN": order_type,
./trader/execution/kis_client.py:538:                "ORD_DVSN": kospi_ord_dvsn,
./tests/test_kis_client.py:219:    """submit_order calls the overseas order endpoint and returns ODNO."""
./tests/test_kis_client.py:224:        if p.endswith("/uapi/overseas-stock/v1/trading/order"):

codex
Your repo currently documents `VTTT1006U` as the paper sell id, which matches the failing call. I’m checking upstream instead of trusting that local note, since this looks like a copied real/paper mapping issue.
exec
/bin/zsh -lc 'git ls-remote https://github.com/koreainvestment/open-trading-api.git HEAD' in /Users/manager/side/makemoney
 succeeded in 2142ms:
33e0e1e65cd1c8c8b639531483ec0b327087bab1	HEAD

exec
/bin/zsh -lc 'git archive --remote=https://github.com/koreainvestment/open-trading-api.git HEAD examples_llm/overseas_stock examples_user/overseas_stock | tar -xO | rg -n "VTTT100|TTTT100|JTTT100|SLL_TYPE|ORD_SVR|order"' in /Users/manager/side/makemoney
exec
/bin/zsh -lc 'git archive --remote=https://github.com/koreainvestment/open-trading-api.git HEAD | tar -t | rg "overseas_stock/.*/(order|.*order|buy|sell|trading)"' in /Users/manager/side/makemoney
 exited 1 in 1678ms:
Invalid command: git-upload-archive 'koreainvestment/open-trading-api.git'
  You appear to be using ssh to clone a git:// URL.
  Make sure your core.gitProxy config option and the
  GIT_PROXY_COMMAND environment variable are NOT set.
fatal: the remote end hung up unexpectedly

 exited 1 in 1704ms:
Invalid command: git-upload-archive 'koreainvestment/open-trading-api.git'
  You appear to be using ssh to clone a git:// URL.
  Make sure your core.gitProxy config option and the
  GIT_PROXY_COMMAND environment variable are NOT set.
fatal: the remote end hung up unexpectedly

codex
GitHub does not allow `git archive` for this repo over HTTPS, so I’m doing a shallow clone into `/tmp` and searching only the relevant overseas stock sample files.
exec
/bin/zsh -lc 'rm -rf /tmp/kis-open-trading-api && git clone --depth 1 https://github.com/koreainvestment/open-trading-api.git /tmp/kis-open-trading-api' in /Users/manager/side/makemoney
 succeeded in 4726ms:
exec
/bin/zsh -lc 'rg --files /tmp/kis-open-trading-api | rg "overseas_stock|overseas"' in /Users/manager/side/makemoney
exec
/bin/zsh -lc 'rg -n "VTTT100|TTTT100|JTTT100|SLL_TYPE|ORD_SVR|ORD_DVSN|OVRS_EXCG_CD|overseas.*order" /tmp/kis-open-trading-api/examples_llm/overseas_stock /tmp/kis-open-trading-api/examples_user/overseas_stock /tmp/kis-open-trading-api/legacy' in /Users/manager/side/makemoney
 succeeded in 0ms:
/tmp/kis-open-trading-api/stocks_info/overseas_stock_code.py
/tmp/kis-open-trading-api/stocks_info/overseas_index_code.py
/tmp/kis-open-trading-api/stocks_info/overseas_future_code.py
/tmp/kis-open-trading-api/MCP/Kis Trading MCP/model/overseas_stock.py
/tmp/kis-open-trading-api/MCP/Kis Trading MCP/model/overseas_futureoption.py
/tmp/kis-open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json
/tmp/kis-open-trading-api/MCP/Kis Trading MCP/configs/overseas_futureoption.json
/tmp/kis-open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions.py
/tmp/kis-open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_functions_ws.py
/tmp/kis-open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_examples.py
/tmp/kis-open-trading-api/examples_user/overseas_futureoption/overseas_futureoption_examples_ws.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/weekly_ccnl/weekly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/weekly_ccnl/chk_weekly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/ccnl/chk_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/ccnl/ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_period_trans/inquire_period_trans.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_period_trans/chk_inquire_period_trans.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_price/opt_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_price/chk_opt_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_price/chk_inquire_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_price/inquire_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/search_opt_detail/chk_search_opt_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/search_opt_detail/search_opt_detail.py
/tmp/kis-open-trading-api/MCP/Kis Trading MCP/tools/overseas_stock.py
/tmp/kis-open-trading-api/MCP/Kis Trading MCP/tools/overseas_futureoption.py
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_examples_ws.py
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_examples.py
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions_ws.py
/tmp/kis-open-trading-api/legacy/websocket/python/ws_overseas_future.py
/tmp/kis-open-trading-api/legacy/websocket/python/ws_overseas_stock.py
/tmp/kis-open-trading-api/legacy/websocket/python/ws_domestic+overseas_stock.py
/tmp/kis-open-trading-api/legacy/websocket/python/ws_domestic_overseas_all.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/chk_inquire_daily_order.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_daily_order/inquire_daily_order.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_unpd/chk_inquire_unpd.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_unpd/inquire_unpd.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/margin_detail/margin_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/margin_detail/chk_margin_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_period_profit/inquire_period_profit.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order_rvsecncl/chk_daytime_order_rvsecncl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order_rvsecncl/daytime_order_rvsecncl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_asking_price/opt_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_asking_price/chk_opt_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_asking_price/inquire_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_asking_price/chk_inquire_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_period_trans/inquire_period_trans.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_period_trans/chk_inquire_period_trans.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/price/price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/price/chk_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/updown_rate/chk_updown_rate.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/updown_rate/updown_rate.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/monthly_ccnl/chk_monthly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/monthly_ccnl/monthly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_monthly_ccnl/chk_opt_monthly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_monthly_ccnl/opt_monthly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/chk_inquire_time_indexchartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/algo_ordno/chk_algo_ordno.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/algo_ordno/algo_ordno.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/daily_ccnl/chk_daily_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/daily_ccnl/daily_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/tick_ccnl/tick_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/tick_ccnl/chk_tick_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/colable_by_company/chk_colable_by_company.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/colable_by_company/colable_by_company.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/market_time/market_time.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/market_time/chk_market_time.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_time_optchartprice/chk_inquire_time_optchartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_time_optchartprice/inquire_time_optchartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/chk_inquire_ccld.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_ccld/inquire_ccld.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/ccnl_notice/ccnl_notice.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/ccnl_notice/chk_ccnl_notice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/inquire_paymt_stdr_balance.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/search_contract_detail/chk_search_contract_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/search_contract_detail/search_contract_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/countries_holiday/countries_holiday.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/countries_holiday/chk_countries_holiday.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/brknews_title/brknews_title.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/brknews_title/chk_brknews_title.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_tick_ccnl/chk_opt_tick_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_tick_ccnl/opt_tick_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/order_rvsecncl/order_rvsecncl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/order_rvsecncl/chk_order_rvsecncl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_psamount/inquire_psamount.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_psamount/chk_inquire_psamount.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_weekly_ccnl/chk_opt_weekly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_weekly_ccnl/opt_weekly_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_daily_ccld/inquire_daily_ccld.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_daily_ccld/chk_inquire_daily_ccld.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/delayed_ccnl/chk_delayed_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/delayed_ccnl/delayed_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_rvsecncl/chk_order_rvsecncl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/stock_detail/stock_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/stock_detail/chk_stock_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_time_futurechartprice/chk_inquire_time_futurechartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_time_futurechartprice/inquire_time_futurechartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/order/chk_order.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/order/order.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_period_ccld/chk_inquire_period_ccld.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_period_ccld/inquire_period_ccld.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_nccs/chk_inquire_nccs.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv_ccnl/order_resv_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv_ccnl/chk_order_resv_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/chk_order.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_vol/chk_trade_vol.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_vol/trade_vol.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/asking_price/asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/asking_price/chk_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_growth/chk_trade_growth.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_growth/trade_growth.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/investor_unpd_trend/investor_unpd_trend.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/investor_unpd_trend/chk_investor_unpd_trend.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/order_notice/chk_order_notice.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/order_notice/order_notice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/ccnl_notice/ccnl_notice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/ccnl_notice/chk_ccnl_notice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/foreign_margin/foreign_margin.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/foreign_margin/chk_foreign_margin.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/delayed_asking_price_asia/delayed_asking_price_asia.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/delayed_asking_price_asia/chk_delayed_asking_price_asia.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_daily_ccnl/chk_opt_daily_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_daily_ccnl/opt_daily_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_pbmn/chk_trade_pbmn.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_pbmn/trade_pbmn.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_detail/chk_opt_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/opt_detail/opt_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/quot_inquire_ccnl/chk_quot_inquire_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/quot_inquire_ccnl/quot_inquire_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/news_title/news_title.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/news_title/chk_news_title.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_psamount/inquire_psamount.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_psamount/chk_inquire_psamount.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv/order_resv.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv/chk_order_resv.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv_list/order_resv_list.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv_list/chk_order_resv_list.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/dailyprice/chk_dailyprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/dailyprice/dailyprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/search_info/chk_search_info.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/search_info/search_info.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/new_highlow/chk_new_highlow.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/new_highlow/new_highlow.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_turnover/chk_trade_turnover.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/trade_turnover/trade_turnover.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/price_detail/chk_price_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/price_detail/price_detail.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/volume_power/chk_volume_power.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/volume_power/volume_power.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/industry_price/chk_industry_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/industry_price/industry_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_asking_price/inquire_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_asking_price/chk_inquire_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/rights_by_ice/chk_rights_by_ice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/rights_by_ice/rights_by_ice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_deposit/inquire_deposit.py
/tmp/kis-open-trading-api/examples_llm/overseas_futureoption/inquire_deposit/chk_inquire_deposit.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/price_fluct/chk_price_fluct.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/price_fluct/price_fluct.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/asking_price/asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/asking_price/chk_asking_price.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/period_rights/chk_period_rights.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/period_rights/period_rights.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_search/inquire_search.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_search/chk_inquire_search.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_algo_ccnl/inquire_algo_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_algo_ccnl/chk_inquire_algo_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/volume_surge/chk_volume_surge.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/volume_surge/volume_surge.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/industry_theme/industry_theme.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/industry_theme/chk_industry_theme.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_ccnl/chk_inquire_ccnl.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order/chk_daytime_order.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order/daytime_order.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/chk_inquire_time_itemchartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/market_cap/market_cap.py
/tmp/kis-open-trading-api/examples_llm/overseas_stock/market_cap/chk_market_cap.py

 succeeded in 0ms:
/tmp/kis-open-trading-api/legacy/rest/kis_api.py:352:        'ORD_DVSN': order_type, 
/tmp/kis-open-trading-api/legacy/rest/kis_api.py:356:        'SLL_TYPE': '01', 
/tmp/kis-open-trading-api/legacy/rest/kis_api.py:433:        "ORD_DVSN": order_dv,
/tmp/kis-open-trading-api/legacy/rest/kis_api.py:535:        "ORD_DVSN": "02", 
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_period_profit/inquire_period_profit.py:123:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/Program.cs:29:        // rt_data = KIS_OverseaStk.get_overseas_order(ord_dv="buy", excg_cd="NASD", itm_no="TSLA", qty=1, unpr=170)
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/Program.cs:30:        // rt_data = KIS_OverseaStk.get_overseas_order(ord_dv="buy", excg_cd="NASD", itm_no="AAPL", qty=1, unpr=216.75)
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv/order_resv.py:23:API_URL = "/uapi/overseas-stock/v1/trading/order-resv"
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv/order_resv.py:163:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv/order_resv.py:176:        params["ORD_SVR_DVSN_CD"] = ord_svr_dvsn_cd
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv/order_resv.py:180:        params["ORD_DVSN"] = ord_dvsn
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order_rvsecncl/daytime_order_rvsecncl.py:25:API_URL = "/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl"
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order_rvsecncl/daytime_order_rvsecncl.py:112:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order_rvsecncl/daytime_order_rvsecncl.py:120:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:198:    api_url = "/uapi/overseas-stock/v1/trading/daytime-order"
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:203:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:209:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:210:        "ORD_DVSN": ord_dvsn,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:322:    api_url = "/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl"
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:327:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:335:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:647:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:845:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:980:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1315:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1505:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1872:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2168:        ord_dvsn (str): [Header tr_id TTTT1002U(미국 매수 주문)] 00 : 지정가 32 : LOO(장개시지정가) 34 : LOC(장마감지정가) * 모의투자 VTTT1002U(미국 매수 주문)로는 00:지정가만 가능  [Header tr_id TTTT1006U(미국 매도 주문)] 00 : 지정가 31 : MOO(장개시시장가) 32 : LOO(장개시지정가) 33 : MOC(장마감시장가) 34 : LOC(장마감지정가) * 모의투자 VTTT1006U(미국 매도 주문)로는 00:지정가만 가능  [Header tr_id TTTS1001U(홍콩 매도 주문)] 00 : 지정가 50 : 단주지정가 * 모의투자 VTTS1001U(홍콩 매도 주문)로는 00:지정가만 가능  [그외 tr_id] 제거
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2223:            tr_id = "TTTT1002U"  # 미국 매수 주문 [모의투자] VTTT1002U
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2242:            tr_id = "TTTT1006U"  # 미국 매도 주문 [모의투자] VTTT1006U
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2270:    api_url = "/uapi/overseas-stock/v1/trading/order"
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2275:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2281:        "SLL_TYPE": sll_type,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2282:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2283:        "ORD_DVSN": ord_dvsn,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2450:    api_url = "/uapi/overseas-stock/v1/trading/order-resv"
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2456:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2469:        params["ORD_SVR_DVSN_CD"] = ord_svr_dvsn_cd
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2473:        params["ORD_DVSN"] = ord_dvsn
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2560:    api_url = "/uapi/overseas-stock/v1/trading/order-resv-ccnl"
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2668:    api_url = "/uapi/overseas-stock/v1/trading/order-resv-list"
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2676:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2795:        tr_id = "TTTT1004U"  # 실전투자용 TR ID
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2797:        tr_id = "VTTT1004U"  # 모의투자용 TR ID
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2801:    api_url = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2806:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:2813:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_period_trans/inquire_period_trans.py:119:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/chk_order.py:51:        - ord_dvsn (str): 주문구분 ([Header tr_id TTTT1002U(미국 매수 주문)] 00 : 지정가 32 : LOO(장개시지정가) 34 : LOC(장마감지정가) * 모의투자 VTTT1002U(미국 매수 주문)로는 00:지정가만 가능  [Header tr_id TTTT1006U(미국 매도 주문)] 00 : 지정가 31 : MOO(장개시시장가) 32 : LOO(장개시지정가) 33 : MOC(장마감시장가) 34 : LOC(장마감지정가) * 모의투자 VTTT1006U(미국 매도 주문)로는 00:지정가만 가능  [Header tr_id TTTS1001U(홍콩 매도 주문)] 00 : 지정가 50 : 단주지정가 * 모의투자 VTTS1001U(홍콩 매도 주문)로는 00:지정가만 가능  [그외 tr_id] 제거)
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:25:API_URL = "/uapi/overseas-stock/v1/trading/order"
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:58:        ord_dvsn (str): [Header tr_id TTTT1002U(미국 매수 주문)] 00 : 지정가 32 : LOO(장개시지정가) 34 : LOC(장마감지정가) * 모의투자 VTTT1002U(미국 매수 주문)로는 00:지정가만 가능  [Header tr_id TTTT1006U(미국 매도 주문)] 00 : 지정가 31 : MOO(장개시시장가) 32 : LOO(장개시지정가) 33 : MOC(장마감시장가) 34 : LOC(장마감지정가) * 모의투자 VTTT1006U(미국 매도 주문)로는 00:지정가만 가능  [Header tr_id TTTS1001U(홍콩 매도 주문)] 00 : 지정가 50 : 단주지정가 * 모의투자 VTTS1001U(홍콩 매도 주문)로는 00:지정가만 가능  [그외 tr_id] 제거
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:113:            tr_id = "TTTT1002U"  # 미국 매수 주문 [모의투자] VTTT1002U
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:130:            tr_id = "TTTT1006U"  # 미국 매도 주문 [모의투자] VTTT1006U
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:159:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:165:        "SLL_TYPE": sll_type,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:166:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py:167:        "ORD_DVSN": ord_dvsn,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv_ccnl/order_resv_ccnl.py:22:API_URL = "/uapi/overseas-stock/v1/trading/order-resv-ccnl"
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py:23:API_URL = "/uapi/overseas-stock/v1/trading/order-rvsecncl"
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py:104:        tr_id = "TTTT1004U"  # 실전투자용 TR ID
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py:106:        tr_id = "VTTT1004U"  # 모의투자용 TR ID
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py:113:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_rvsecncl/order_rvsecncl.py:120:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:40:            string url = "/uapi/overseas-stock/v1/trading/order";
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:50:                        trID = "TTTT1002U"; // 미국 매수 주문 [모의투자] VTTT1002U
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:80:                        trID = "TTTT1006U"; // 미국 매도 주문 [모의투자] VTTT1006U
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:133:                { "OVRS_EXCG_CD", excg_cd },                    // 해외거래소코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:135:                { "ORD_DVSN", ord_dvsn },                       // 주문구분 00:지정가, 01:시장가, 02:조건부지정가  나머지주문구분 API 문서 참조
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:140:                { "SLL_TYPE", sll_type },                       // 판매유형
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:141:                { "ORD_SVR_DVSN_CD", "0" }                      // 주문서버구분코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:167:            string url = "/uapi/overseas-stock/v1/trading/order-rvsecncl";
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:176:                    trID = "TTTT1004U"; // 미국 매수 주문 [모의투자] VTTT1004U
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:215:                { "OVRS_EXCG_CD", excg_cd },            // 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:222:                { "ORD_SVR_DVSN_CD", "0" }              // 주문서버구분코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:260:                { "OVRS_EXCG_CD", excg_cd }, // 해외거래소코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:342:                { "OVRS_EXCG_CD", excg_cd }, // 해외거래소코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:409:                { "OVRS_EXCG_CD", excg_cd }, // 해외거래소코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:443:                { "OVRS_EXCG_CD", excg_cd }, // 해외거래소코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:543:                { "OVRS_EXCG_CD", excgCd},
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:682:                { "OVRS_EXCG_CD", dvsn },                  // 원화외화구분코드 01 : 원화, 02 : 외화
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:707:            string url = "/uapi/overseas-stock/v1/trading/daytime-order";
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:752:                { "OVRS_EXCG_CD", excg_cd },                // 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:754:                { "ORD_DVSN", "00" },                       // 주문구분 00:지정가 * 주간거래는 지정가만 가능
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:759:                { "ORD_SVR_DVSN_CD", "0" }                  // 주문서버구분코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:782:            string url = "/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl";
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:819:                { "OVRS_EXCG_CD", excg_cd },            // 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:827:                { "ORD_SVR_DVSN_CD", "0" }              // 주문서버구분코드
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:868:                { "OVRS_EXCG_CD", excg_cd },                // 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:920:                { "OVRS_EXCG_CD", excg_cd },                // 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:1026:                { "OVRS_EXCG_CD", excg_cd },                // 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:1099:                { "OVRS_EXCG_CD", excg_cd },  // 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_nccs/inquire_nccs.py:97:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv_list/order_resv_list.py:24:API_URL = "/uapi/overseas-stock/v1/trading/order-resv-list"
/tmp/kis-open-trading-api/examples_llm/overseas_stock/order_resv_list/order_resv_list.py:115:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_psamount/inquire_psamount.py:103:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:209:							"raw": "{\r\n\t\"CANO\": \"{{CANO_REAL}}\",\r\n\t\"ACNT_PRDT_CD\": \"01\",\r\n\t\"PDNO\": \"071050\",\r\n\t\"ORD_DVSN\": \"01\",\r\n\t\"ORD_QTY\": \"1\",\r\n\t\"ORD_UNPR\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:375:							"raw": "{\r\n\t\"CANO\": \"{{CANO_REAL_T}}\",\r\n\t\"ACNT_PRDT_CD\": \"03\",\r\n\t\"PDNO\": \"071050\",\r\n\t\"ORD_DVSN\": \"01\",\r\n\t\"ORD_QTY\": \"1\",\r\n\t\"ORD_UNPR\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:484:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"136480\",\r\n    \"ORD_DVSN\": \"00\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"ORD_UNPR\": \"2500\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:588:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"005930\",\r\n    \"CRDT_TYPE\": \"21\",\r\n    \"LOAN_DT\": \"20220810\",\r\n    \"ORD_DVSN\": \"00\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"ORD_UNPR\": \"55000\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:692:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"KRX_FWDG_ORD_ORGNO\": \"06010\",\r\n    \"ORGN_ODNO\": \"0000002101\",\r\n    \"ORD_DVSN\": \"00\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"02\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"ORD_UNPR\": \"55000\",\r\n    \"QTY_ALL_ORD_YN\": \"Y\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1197:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-psbl-order?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&PDNO=005930&ORD_UNPR=55000&ORD_DVSN=01&OVRS_ICLD_YN=N&CMA_EVLU_AMT_ICLD_YN=N",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1230:											"key": "ORD_DVSN",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1329:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"005930\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"ORD_UNPR\": \"55000\",\r\n    \"SLL_BUY_DVSN_CD\": \"02\",\r\n    \"ORD_DVSN_CD\": \"00\",\r\n    \"ORD_OBJT_CBLC_DVSN_CD\": \"10\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1535:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"005930\",\r\n    \"ORD_QTY\": \"2\",\r\n    \"ORD_UNPR\": \"55000\",\r\n    \"SLL_BUY_DVSN_CD\": \"02\",\r\n    \"ORD_DVSN_CD\": \"00\",\r\n    \"ORD_OBJT_CBLC_DVSN_CD\": \"10\",\r\n    \"RSVN_ORD_SEQ\": \"88793\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2027:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/pension/inquire-psbl-order?CANO={{CANO_REAL}}&ACNT_PRDT_CD=29&PDNO=069500&ORD_UNPR=30800&ORD_DVSN=00&CMA_EVLU_AMT_ICLD_YN=Y&ACCA_DVSN_CD=00",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2061:											"key": "ORD_DVSN",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2488:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-credit-psamount?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&PDNO=005930&ORD_UNPR=60000&ORD_DVSN=01&CRDT_TYPE=21&OVRS_ICLD_YN=N&CMA_EVLU_AMT_ICLD_YN=N",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2521:											"key": "ORD_DVSN",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:15730:									"raw": "{\r\n    \"ORD_PRCS_DVSN_CD\": \"02\",\r\n    \"CANO\": \"{{CANO_REAL_T}}\",\r\n    \"ACNT_PRDT_CD\": \"03\",\r\n    \"SLL_BUY_DVSN_CD\": \"02\",\r\n    \"SHTN_PDNO\": \"167R12\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"UNIT_PRICE\": \"0\",\r\n    \"NMPR_TYPE_CD\": \"02\",\r\n    \"KRX_NMPR_CNDT_CD\": \"0\",\r\n    \"ORD_DVSN_CD\": \"02\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:15834:									"raw": "{\r\n    \"ORD_PRCS_DVSN_CD\": \"02\",\r\n    \"CANO\": \"{{CANO_REAL_T}}\",\r\n    \"ACNT_PRDT_CD\": \"03\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"02\",\r\n    \"ORGN_ODNO\": \"0000004018\",\r\n    \"ORD_QTY\": \"\",\r\n    \"UNIT_PRICE\": \"0\",\r\n    \"NMPR_TYPE_CD\": \"02\",\r\n    \"KRX_NMPR_CNDT_CD\": \"0\",\r\n    \"RMN_QTY_YN\": \"Y\",\r\n    \"ORD_DVSN_CD\": \"01\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16188:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-psbl-order?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&PDNO=101S03&SLL_BUY_DVSN_CD=02&UNIT_PRICE=1&ORD_DVSN_CD=01",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16226:											"key": "ORD_DVSN_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16599:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-psbl-ngt-order?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&PDNO=101T03&PRDT_TYPE_CD=301&SLL_BUY_DVSN_CD=02&UNIT_PRICE=322&ORD_DVSN_CD=01",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16642:											"key": "ORD_DVSN_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18193:										"value": "TTTT1002U",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18194:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18207:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"PDNO\": \"TSLA\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"OVRS_ORD_UNPR\": \"900.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18215:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18301:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18314:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"PDNO\": \"4689\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"450.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18322:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18409:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18422:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"SHAA\",\r\n    \"PDNO\": \"601360\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"7.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18430:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18517:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18530:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"SEHK\",\r\n    \"PDNO\": \"08495\",\r\n    \"ORD_QTY\": \"4000\",\r\n    \"OVRS_ORD_UNPR\": \"1.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18538:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18625:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18638:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"SZAA\",\r\n    \"PDNO\": \"002051\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"8.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18646:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18732:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18745:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"VND\",\r\n    \"PDNO\": \"HPG\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"23000.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18753:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18838:										"value": "TTTT1004U",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18839:										"description": "[실전투자]\nTTTT1004U : 미국 정정 취소 주문\nTTTS1003U : 홍콩 정정 취소 주문\nTTTS0309U : 일본 정정 취소 주문\nTTTS0302U : 상해 취소 주문\nTTTS0306U : 심천 취소 주문\nTTTS0312U : 베트남 취소 주문\n\n[모의투자]\nVTTT1004U : 미국 정정 취소 주문\nVTTS1003U : 홍콩 정정 취소 주문\nVTTS0309U : 일본 정정 취소 주문\nVTTS0302U : 상해 취소 주문\nVTTS0306U : 심천 취소 주문\nVTTS0312U : 베트남 취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18852:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"PDNO\": \"4689\",\r\n    \"ORGN_ODNO\": \"0000006616\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"01\",\r\n    \"ORD_QTY\": \"200\",\r\n    \"OVRS_ORD_UNPR\": \"450.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18860:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18945:										"value": "TTTT1004U ",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18946:										"description": "[실전투자]\nTTTT1004U : 미국 정정 취소 주문\nTTTS1003U : 홍콩 정정 취소 주문\nTTTS0309U : 일본 정정 취소 주문\nTTTS0302U : 상해 취소 주문\nTTTS0306U : 심천 취소 주문\nTTTS0312U : 베트남 취소 주문\n\n[모의투자]\nVTTT1004U : 미국 정정 취소 주문\nVTTS1003U : 홍콩 정정 취소 주문\nVTTS0309U : 일본 정정 취소 주문\nVTTS0302U : 상해 취소 주문\nVTTS0306U : 심천 취소 주문\nVTTS0312U : 베트남 취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18959:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"PDNO\": \"4689\",\r\n    \"ORGN_ODNO\": \"0000006616\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"02\",\r\n    \"ORD_QTY\": \"200\",\r\n    \"OVRS_ORD_UNPR\": \"450.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18967:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19063:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"TSLA\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"FT_ORD_QTY\": \"1\",\r\n    \"FT_ORD_UNPR3\": \"900.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19071:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19167:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"4689\",\r\n    \"PRDT_TYPE_CD\": \"515\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"450.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19175:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19271:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"08495\",\r\n    \"PRDT_TYPE_CD\": \"501\",\r\n    \"OVRS_EXCG_CD\": \"SEHK\",\r\n    \"FT_ORD_QTY\": \"4000\",\r\n    \"FT_ORD_UNPR3\": \"1.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19279:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19375:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"601360\",\r\n    \"PRDT_TYPE_CD\": \"551\",\r\n    \"OVRS_EXCG_CD\": \"SHAA\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"7.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19383:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19479:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"002051\",\r\n    \"PRDT_TYPE_CD\": \"552\",\r\n    \"OVRS_EXCG_CD\": \"SZAA\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"8.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19487:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19583:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"HPG\",\r\n    \"PRDT_TYPE_CD\": \"508\",\r\n    \"OVRS_EXCG_CD\": \"HASE\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"23000.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19591:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19695:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv-ccnl",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19765:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-nccs?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=TKSE&SORT_SQN=DS&CTX_AREA_FK200=&CTX_AREA_NK200=",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19788:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19867:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=NASD&TR_CRCY_CD=USD&CTX_AREA_FK200=&CTX_AREA_NK200",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19890:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19969:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-ccnl?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&PDNO=&ORD_STRT_DT=&ORD_END_DT=&SLL_BUY_DVSN=00&CCLD_NCCS_DVSN=00&OVRS_EXCG_CD=NASD&SORT_SQN=DS&ORD_DT=&ORD_GNO_BRNO=&ODNO=&CTX_AREA_FK200=&CTX_AREA_NK200=",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20017:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20213:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/order-resv-list?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&INQR_STRT_DT=20220809&INQR_END_DT=20220830&INQR_DVSN_CD=00&PRDT_TYPE_CD=512&OVRS_EXCG_CD=NASD&CTX_AREA_FK200&CTX_AREA_NK200",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20256:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20330:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-psamount?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=NASD&OVRS_ORD_UNPR=1.4&ITEM_CD=TRVG",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20353:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20458:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"PDNO\": \"DLPN\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"OVRS_ORD_UNPR\": \"0.8\",\r\n\t\"CTAC_TLNO\": \"\",\r\n\t\"MGCO_APTM_ODNO\": \"\",\r\n\t\"ORD_SVR_DVSN_CD\": \"0\",\r\n\t\"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20466:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/daytime-order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20565:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"PDNO\": \"GRAB\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"OVRS_ORD_UNPR\": \"2.86\",\r\n\t\"CTAC_TLNO\": \"\",\r\n\t\"MGCO_APTM_ODNO\": \"\",\r\n\t\"ORD_SVR_DVSN_CD\": \"0\",\r\n\t\"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20573:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/daytime-order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20672:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"PDNO\": \"DLPN\",\r\n    \"ORGN_ODNO\": \"14\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"01\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"OVRS_ORD_UNPR\": \"1.9\",\r\n    \"CTAC_TLNO\": \"\",\r\n\t\"MGCO_APTM_ODNO\": \"\",\r\n\t\"ORD_SVR_DVSN_CD\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20680:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20779:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"PDNO\": \"DLPN\",\r\n    \"ORGN_ODNO\": \"169\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"02\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"OVRS_ORD_UNPR\": \"1.9\",\r\n    \"CTAC_TLNO\": \"\",\r\n\t\"MGCO_APTM_ODNO\": \"\",\r\n\t\"ORD_SVR_DVSN_CD\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20787:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20862:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-period-profit?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=NASD&NATN_CD=&CRCY_CD=USD&PDNO=&INQR_STRT_DT=20231001&INQR_END_DT=20231023&WCRC_FRCR_DVSN_CD=01&CTX_AREA_FK200=&CTX_AREA_NK200=",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20885:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:21067:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-period-trans?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&ERLM_STRT_DT=20240101&ERLM_END_DT=20240625&OVRS_EXCG_CD=&PDNO=&SLL_BUY_DVSN_CD=00&LOAN_DVSN_CD=&CTX_AREA_FK100=&CTX_AREA_NK100=",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:21100:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:22947:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL_T}}\",\r\n    \"ACNT_PRDT_CD\": \"08\",\r\n    \"OVRS_FUTR_FX_PDNO\": \"6BZ22\",\r\n    \"SLL_BUY_DVSN_CD\": \"02\",\r\n    \"FM_LQD_USTL_CCLD_DT\": \"\",\r\n    \"FM_LQD_USTL_CCNO\": \"\",\r\n    \"PRIC_DVSN_CD\": \"1\",\r\n    \"FM_LIMIT_ORD_PRIC\": \"1.17\",\r\n    \"FM_STOP_ORD_PRIC\": \"\",\r\n    \"FM_ORD_QTY\": \"1\",\r\n    \"FM_LQD_LMT_ORD_PRIC\": \"\",\r\n    \"FM_LQD_STOP_ORD_PRIC\": \"\",\r\n    \"CCLD_CNDT_CD\": \"6\",\r\n    \"CPLX_ORD_DVSN_CD\": \"0\",\r\n    \"ECIS_RSVN_ORD_YN\": \"N\",\r\n    \"FM_HDGE_ORD_SCRN_YN\": \"N\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:22955:									"raw": "{{PROD}}/uapi/overseas-futureoption/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:23059:									"raw": "{{PROD}}/uapi/overseas-futureoption/v1/trading/order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:23163:									"raw": "{{PROD}}/uapi/overseas-futureoption/v1/trading/order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:23993:									"raw": "{{PROD}}/uapi/overseas-futureoption/v1/trading/inquire-daily-order?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=08&STRT_DT=20220801&END_DT=20221117&FM_PDGR_CD=&CCLD_NCCS_DVSN=00&SLL_BUY_DVSN_CD=%%&FUOP_DVSN=00&CTX_AREA_FK200&CTX_AREA_NK200",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25446:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"KR6095572D81\",\r\n    \"ORD_QTY2\": \"1\",\r\n    \"BOND_ORD_UNPR\":\"10000.0\",\r\n    \"SAMT_MKET_PTCI_YN\":\"N\",\r\n    \"BOND_RTL_MKET_YN\":\"N\",\r\n    \"IDCR_STFNO\":\"\",\r\n    \"MGCO_APTM_ODNO\":\"\",\r\n    \"ORD_SVR_DVSN_CD\":\"0\",\r\n    \"CTAC_TLNO\":\"\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25532:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"ORD_DVSN\":\"01\",\r\n    \"PDNO\":\"KR6095572D81\",\r\n    \"ORD_QTY2\":\"1\",\r\n    \"BOND_ORD_UNPR\":\"10450.0\",\r\n    \"SPRX_YN\":\"N\",\r\n    \"BUY_DT\":\"\",\r\n    \"BUY_SEQ\":\"\",\r\n    \"SAMT_MKET_PTCI_YN\":\"N\",\r\n    \"SLL_AGCO_OPPS_SLL_YN\":\"N\",\r\n    \"BOND_RTL_MKET_YN\":\"N\",\r\n    \"MGCO_APTM_ODNO\":\"\",\r\n    \"ORD_SVR_DVSN_CD\":\"0\",\r\n    \"CTAC_TLNO\":\"\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25618:									"raw": "{\r\n    \"CANO\": \"{{CANO_REAL}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"KR6095572D81\",\r\n    \"ORGN_ODNO\": \"0000017402\",\r\n    \"ORD_QTY2\": \"2\",\r\n    \"BOND_ORD_UNPR\": \"10451\",\r\n    \"QTY_ALL_ORD_YN\": \"Y\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"01\",\r\n    \"MGCO_APTM_ODNO\": \"\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"CTAC_TLNO\": \"\"\r\n}",
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_ccnl/inquire_ccnl.py:143:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order/daytime_order.py:25:API_URL = "/uapi/overseas-stock/v1/trading/daytime-order"
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order/daytime_order.py:115:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order/daytime_order.py:121:        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/daytime_order/daytime_order.py:122:        "ORD_DVSN": ord_dvsn,
/tmp/kis-open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:105:        "OVRS_EXCG_CD": ovrs_excg_cd,
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:34:def get_overseasfuopt_order(itm_no="", ord_dv="", dvsn="", qty=0, limt_pric=0, stop_pric=0, ccld_cd="6", tr_cont="", FK100="", NK100="", dataframe=None):
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:35:    url = '/uapi/overseas-futureoption/v1/trading/order'
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:72:        "CPLX_ORD_DVSN_CD": "0",                # 복합주문구분코드
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:94:def get_overseasfuopt_order_rvsecncl(dvsn="", ord_dt="", orgn_odno="", limt_pric=0, stop_pric=0, lqd_limt_pric=0, lqd_stop_pric=0, tr_cont="", dataframe=None):
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:95:    url = '/uapi/overseas-futureoption/v1/trading/order-rvsecncl'
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:478:def get_overseasfuopt_inquire_daily_order(fr_dt="", to_dt="", ccld_dvsn="01", dvsn="%%", fuop_dvsn="00", tr_cont="", FK100="", NK100="", dataframe=None):
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:479:    url = '/uapi/overseas-futureoption/v1/trading/inquire-daily-order'
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt.py:539:        return get_overseasfuopt_inquire_daily_order(fr_dt, to_dt, ccld_dvsn, dvsn, fuop_dvsn, "N", FK100, NK100, dataframe)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk_ws.py:357:            # rt_data = kb.get_overseas_order(ord_dv="buy", excg_cd=excg_df, itm_no=stock_df, qty=1, unpr=123.3)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk_ws.py:360:            # rt_data = kb.get_overseas_daytime_order(ord_dv="buy", excg_cd=excg_df, itm_no=stock_df, qty=1, unpr=123.3)
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:209:							"raw": "{\r\n\t\"CANO\": \"{{CANO}}\",\r\n\t\"ACNT_PRDT_CD\": \"01\",\r\n\t\"PDNO\": \"071050\",\r\n\t\"ORD_DVSN\": \"01\",\r\n\t\"ORD_QTY\": \"1\",\r\n\t\"ORD_UNPR\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:375:							"raw": "{\r\n\t\"CANO\": \"{{CANO_T}}\",\r\n\t\"ACNT_PRDT_CD\": \"03\",\r\n\t\"PDNO\": \"071050\",\r\n\t\"ORD_DVSN\": \"01\",\r\n\t\"ORD_QTY\": \"1\",\r\n\t\"ORD_UNPR\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1568:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"005930\",\r\n    \"ORD_DVSN\": \"00\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"ORD_UNPR\": \"55000\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1671:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"KRX_FWDG_ORD_ORGNO\": \"00950\",\r\n    \"ORGN_ODNO\": \"6635\",\r\n    \"ORD_DVSN\": \"00\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"02\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"ORD_UNPR\": \"55000\",\r\n    \"QTY_ALL_ORD_YN\": \"Y\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2060:									"raw": "{{VTS}}/uapi/domestic-stock/v1/trading/inquire-psbl-order?CANO={{CANO}}&ACNT_PRDT_CD=01&PDNO=005930&ORD_UNPR=55000&ORD_DVSN=01&OVRS_ICLD_YN=N&CMA_EVLU_AMT_ICLD_YN=N",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2093:											"key": "ORD_DVSN",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2203:									"raw": "{\r\n    \"ORD_PRCS_DVSN_CD\": \"02\",\r\n    \"CANO\": \"{{CANO_T}}\",\r\n    \"ACNT_PRDT_CD\": \"03\",\r\n    \"SLL_BUY_DVSN_CD\": \"02\",\r\n    \"SHTN_PDNO\": \"101S09\",\r\n    \"ORD_QTY\": \"10\",\r\n    \"UNIT_PRICE\": \"300\",\r\n    \"NMPR_TYPE_CD\": \"01\",\r\n    \"KRX_NMPR_CNDT_CD\": \"0\",\r\n    \"ORD_DVSN_CD\": \"01\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2307:									"raw": "{\r\n    \"ORD_PRCS_DVSN_CD\": \"02\",\r\n    \"CANO\": \"{{CANO_T}}\",\r\n    \"ACNT_PRDT_CD\": \"03\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"02\",\r\n    \"ORGN_ODNO\": \"0000004018\",\r\n    \"ORD_QTY\": \"10\",\r\n    \"UNIT_PRICE\": \"300\",\r\n    \"NMPR_TYPE_CD\": \"01\",\r\n    \"KRX_NMPR_CNDT_CD\": \"0\",\r\n    \"RMN_QTY_YN\": \"Y\",\r\n    \"ORD_DVSN_CD\": \"01\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2661:									"raw": "{{VTS}}/uapi/domestic-futureoption/v1/trading/inquire-psbl-order?CANO={{CANO_T}}&ACNT_PRDT_CD=03&PDNO=101S09&SLL_BUY_DVSN_CD=02&UNIT_PRICE=1&ORD_DVSN_CD=01",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2699:											"key": "ORD_DVSN_CD",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3037:										"value": "VTTT1002U",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3039:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3051:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"PDNO\": \"TSLA\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"OVRS_ORD_UNPR\": \"900.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3059:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3143:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3155:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"PDNO\": \"4689\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"450.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3163:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3247:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3259:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"SHAA\",\r\n    \"PDNO\": \"601360\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"7.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3267:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3351:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3363:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"SEHK\",\r\n    \"PDNO\": \"08495\",\r\n    \"ORD_QTY\": \"4000\",\r\n    \"OVRS_ORD_UNPR\": \"1.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3371:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3455:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3467:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"SZAA\",\r\n    \"PDNO\": \"002051\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"8.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3475:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3559:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3571:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"VND\",\r\n    \"PDNO\": \"HPG\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"23000.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3579:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3663:										"description": "[실전투자]\nTTTT1004U : 미국 정정 취소 주문\nTTTS1003U : 홍콩 정정 취소 주문\nTTTS0309U : 일본 정정 취소 주문\nTTTS0302U : 상해 취소 주문\nTTTS0306U : 심천 취소 주문\nTTTS0312U : 베트남 취소 주문\n\n[모의투자]\nVTTT1004U : 미국 정정 취소 주문\nVTTS1003U : 홍콩 정정 취소 주문\nVTTS0309U : 일본 정정 취소 주문\nVTTS0302U : 상해 취소 주문\nVTTS0306U : 심천 취소 주문\nVTTS0312U : 베트남 취소 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3675:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"PDNO\": \"4689\",\r\n    \"ORGN_ODNO\": \"0000006616\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"01\",\r\n    \"ORD_QTY\": \"200\",\r\n    \"OVRS_ORD_UNPR\": \"450.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3683:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3767:										"description": "[실전투자]\nTTTT1004U : 미국 정정 취소 주문\nTTTS1003U : 홍콩 정정 취소 주문\nTTTS0309U : 일본 정정 취소 주문\nTTTS0302U : 상해 취소 주문\nTTTS0306U : 심천 취소 주문\nTTTS0312U : 베트남 취소 주문\n\n[모의투자]\nVTTT1004U : 미국 정정 취소 주문\nVTTS1003U : 홍콩 정정 취소 주문\nVTTS0309U : 일본 정정 취소 주문\nVTTS0302U : 상해 취소 주문\nVTTS0306U : 심천 취소 주문\nVTTS0312U : 베트남 취소 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3779:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"PDNO\": \"4689\",\r\n    \"ORGN_ODNO\": \"0000006616\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"02\",\r\n    \"ORD_QTY\": \"200\",\r\n    \"OVRS_ORD_UNPR\": \"450.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3787:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-rvsecncl",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3883:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"PDNO\": \"TSLA\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"FT_ORD_QTY\": \"1\",\r\n    \"FT_ORD_UNPR3\": \"900.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3891:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3987:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"4689\",\r\n    \"PRDT_TYPE_CD\": \"515\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"450.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3995:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4091:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"08495\",\r\n    \"PRDT_TYPE_CD\": \"501\",\r\n    \"OVRS_EXCG_CD\": \"SEHK\",\r\n    \"FT_ORD_QTY\": \"4000\",\r\n    \"FT_ORD_UNPR3\": \"1.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4099:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4195:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"601360\",\r\n    \"PRDT_TYPE_CD\": \"551\",\r\n    \"OVRS_EXCG_CD\": \"SHAA\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"7.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4203:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4299:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"002051\",\r\n    \"PRDT_TYPE_CD\": \"552\",\r\n    \"OVRS_EXCG_CD\": \"SZAA\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"8.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4307:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4404:									"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"RVSE_CNCL_DVSN_CD\": \"00\",\r\n    \"PDNO\": \"HPG\",\r\n    \"PRDT_TYPE_CD\": \"508\",\r\n    \"OVRS_EXCG_CD\": \"HASE\",\r\n    \"FT_ORD_QTY\": \"100\",\r\n    \"FT_ORD_UNPR3\": \"23000.0\"\r\n}",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4412:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4516:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order-resv",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4586:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-nccs?CANO={{CANO}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=TKSE&SORT_SQN=DS&CTX_AREA_FK200=&CTX_AREA_NK200",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4609:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4688:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=TKSE&TR_CRCY_CD=JPY&CTX_AREA_FK200=&CTX_AREA_NK200=",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4711:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4790:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-ccnl?CANO={{CANO}}&ACNT_PRDT_CD=01&PDNO=&ORD_STRT_DT=&ORD_END_DT=&SLL_BUY_DVSN=00&CCLD_NCCS_DVSN=00&OVRS_EXCG_CD=&SORT_SQN=DS&ORD_DT=&ORD_GNO_BRNO=&ODNO=&CTX_AREA_NK200=&CTX_AREA_FK200=",
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4838:											"key": "OVRS_EXCG_CD",
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:20:# 지정가 기준이며 시장가 옵션(주문구분코드)을 사용하는 경우 kis_ovrseastk.py get_overseas_order 수정요망!
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:21:#rt_data = kb.get_overseas_order(ord_dv="buy", excg_cd="NASD", itm_no="TSLA", qty=1, unpr=170)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:22:#rt_data = kb.get_overseas_order(ord_dv="buy", excg_cd="NASD", itm_no="AAPL", qty=1, unpr=216.75)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:23:rt_data = kb.get_overseas_order(ord_dv="buy", excg_cd="NASD", itm_no="NVDA", qty=1, unpr=123.3)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:27:# 지정가 기준이며 시장가 옵션(주문구분코드)을 사용하는 경우 kis_ovrseastk.py get_overseas_order 수정요망!
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:28:rt_data = kb.get_overseas_order_rvsecncl(excg_cd="NASD", itm_no="TSLA", orgn_odno="0030089601", rvse_cncl_dvsn_cd="02", qty=1, unpr=0)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:38:rt_data = kb.get_overseas_order_allcncl(excg_cd="NASD", itm_no="")
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:68:# 지정가 기준이며 시장가 옵션(주문구분코드)을 사용하는 경우 kis_ovrseastk.py get_overseas_order 수정요망!
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:69:#rt_data = kb.get_overseas_daytime_order(ord_dv="buy", excg_cd="NASD", itm_no="TSLA", qty=1, unpr=251)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:70:#rt_data = kb.get_overseas_daytime_order(ord_dv="buy", excg_cd="NASD", itm_no="AAPL", qty=1, unpr=216.75)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:71:rt_data = kb.get_overseas_daytime_order(ord_dv="buy", excg_cd="NASD", itm_no="NVDA", qty=1, unpr=123.3)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:75:# 지정가 기준이며 시장가 옵션(주문구분코드)을 사용하는 경우 kis_ovrseastk.py get_overseas_order 수정요망!
/tmp/kis-open-trading-api/legacy/Sample01/kis_api03.py:76:rt_data = kb.get_overseas_daytime_order_rvsecncl(excg_cd="NASD", itm_no="TSLA", orgn_odno="0030089601", rvse_cncl_dvsn_cd="02", qty=1, unpr=0)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api04.py:22:rt_data = kb.get_overseasfuopt_order(itm_no="OESU24 C6000", ord_dv="02", dvsn="1", qty=1, limt_pric=13.75, stop_pric=0)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api04.py:26:rt_data = kb.get_overseasfuopt_order_rvsecncl(dvsn="01", ord_dt="", orgn_odno="", limt_pric=0, stop_pric=0, lqd_limt_pric=0, lqd_stop_pric=0)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api04.py:30:rt_data = kb.get_overseasfuopt_order_rvsecncl(dvsn="01", ord_dt="", orgn_odno="", limt_pric=0, stop_pric=0, lqd_limt_pric=0, lqd_stop_pric=0)
/tmp/kis-open-trading-api/legacy/Sample01/kis_api04.py:63:rt_data = kb.get_overseasfuopt_inquire_daily_order(fr_dt="20240401", to_dt="", ccld_dvsn="01", dvsn="%%", fuop_dvsn="00")
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt_ws.py:205:                'CPLX_ORD_DVSN_CD',	# 복합주문구분코드 0 (HEDGE청산만 이용)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt_ws.py:228:                'AUTO_ORD_DVSN_CD']	# 자동주문 전략구분
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt_ws.py:240:                'CPLX_ORD_DVSN_CD',	# 복합주문구분코드',	# 0 (HEDGE청산만 이용)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseafuopt_ws.py:400:            # rt_data = kb.get_overseasfuopt_order(itm_no=stock_df, ord_dv="02", dvsn="1", qty=ord_qty, limt_pric=val1, stop_pric=0)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:45:def get_overseas_order(ord_dv="", excg_cd="", itm_no="", qty=0, unpr=0, tr_cont="", FK100="", NK100="", dataframe=None):  # 국내주식주문 > 주식주문(현금)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:46:    url = '/uapi/overseas-stock/v1/trading/order'
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:50:            tr_id = "TTTT1002U"  # 미국 매수 주문 [모의투자] VTTT1002U
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:66:            tr_id = "TTTT1006U"  # 미국 매도 주문 [모의투자] VTTT1006U
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:107:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:110:        "ORD_DVSN": "00",                       # 주문구분 00:지정가, 01:시장가, 02:조건부지정가  나머지주문구분 API 문서 참조
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:113:        "SLL_TYPE": sll_type,                   # 판매유형
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:114:        "ORD_SVR_DVSN_CD": "0"                  # 주문서버구분코드l
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:134:def get_overseas_order_rvsecncl(excg_cd="", itm_no="", orgn_odno="", rvse_cncl_dvsn_cd="", qty=0, unpr=0, tr_cont="", dataframe=None):
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:135:    url = '/uapi/overseas-stock/v1/trading/order-rvsecncl'
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:138:        tr_id = "TTTT1004U"  # 미국 매수 주문 [모의투자] VTTT1004U
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:168:        "OVRS_EXCG_CD": excg_cd,            # 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:175:        "ORD_SVR_DVSN_CD": "0"              # 주문서버구분코드
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:196:def get_overseas_order_allcncl(excg_cd="", itm_no="", tr_cont="", FK100="", NK100="", dataframe=None):
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:209:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:248:            res_cncl = get_overseas_order_rvsecncl(excg_cd="NASD", itm_no="", orgn_odno=r_odno, rvse_cncl_dvsn_cd="02")
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:256:        return get_overseas_order_allcncl(excg_cd, itm_no, "N", FK100, NK100, dataframe)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:290:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:361:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:406:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:489:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드, 전종목일 경우 "%" 입력, NASD:미국시장 전체(나스닥,뉴욕,아멕스),NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:626:        "OVRS_EXCG_CD": dvsn,              # 원화외화구분코드 01 : 원화, 02 : 외화
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:669:def get_overseas_daytime_order(ord_dv="", excg_cd="", itm_no="", qty=0, unpr=0, tr_cont="", FK100="", NK100="", dataframe=None):  # 국내주식주문 > 주식주문(현금)
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:670:    url = '/uapi/overseas-stock/v1/trading/daytime-order'
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:699:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:701:        "ORD_DVSN": "00",                       # 주문구분 00:지정가 * 주간거래는 지정가만 가능
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:706:        "ORD_SVR_DVSN_CD": "0"                  # 주문서버구분코드
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:726:def get_overseas_daytime_order_rvsecncl(excg_cd="", itm_no="", orgn_odno="", rvse_cncl_dvsn_cd="", qty=0, unpr=0, tr_cont="", dataframe=None):
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:727:    url = '/uapi/overseas-stock/v1/trading/daytime-order-rvsecncl'
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:754:        "OVRS_EXCG_CD": excg_cd,            # 해외거래소코드 NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:762:        "ORD_SVR_DVSN_CD": "0"              # 주문서버구분코드
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:812:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:856:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:964:        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py:1028:        "OVRS_EXCG_CD": excg_cd,  # 해외거래소코드, 공란:전체,NASD:미국,SEHK:홍콩,SHAA:중국,TKSE:일본,HASE:베트남
/tmp/kis-open-trading-api/legacy/Sample01/kis_domstk.py:54:        "ORD_DVSN": "00",                       # 주문구분 00:지정가, 01:시장가, 02:조건부지정가  나머지주문구분 API 문서 참조
/tmp/kis-open-trading-api/legacy/Sample01/kis_domstk.py:113:        "ORD_DVSN": ord_dvsn,                   # 주문구분 00:지정가, 01:시장가, 02:조건부지정가  나머지주문구분 API 문서 참조
/tmp/kis-open-trading-api/legacy/Sample01/kis_domstk.py:375:        "ORD_UNPR": ord_unpr,                       # 주문단가   1주당 가격 ※ 시장가(ORD_DVSN:01)로 조회 시, 공란으로 입력
/tmp/kis-open-trading-api/legacy/Sample01/kis_domstk.py:376:        "ORD_DVSN": "00",                           # 주문구분 공란 시, 매수수량 없이 매수금액만 조회됨 00 : 지정가,01 : 시장가,02 : 조건부지정가,03 : 최유리지정가
/tmp/kis-open-trading-api/legacy/Sample01/kis_domstk.py:454:        "ORD_DVSN_CD": "00",                    # 주문구분 00:지정가, 01:시장가, 02:조건부지정가, 05 : 장전 시간외
/tmp/kis-open-trading-api/legacy/Sample01/kis_domstk.py:548:        "ORD_DVSN_CD": ord_dvsn,                # 주문구분 	[정정]00 : 지정가, 01 : 시장가, 02 : 조건부지정가, 05 : 장전 시간외
/tmp/kis-open-trading-api/legacy/Sample01/kis_domstk.py:716:        "ORD_DVSN": "00",                        # 주문구분 00: 지정가
/tmp/kis-open-trading-api/legacy/Sample01/kis_domfuopt.py:61:        "NMPR_TYPE_CD": "",                     # 호가유형코드 ※ ORD_DVSN_CD(주문구분코드)를 입력한 경우 ""(공란)으로 입력해도 됨
/tmp/kis-open-trading-api/legacy/Sample01/kis_domfuopt.py:62:        "KRX_NMPR_CNDT_CD": "",                 # 한국거래소호가조건코드 ※ ORD_DVSN_CD(주문구분코드)를 입력한 경우 ""(공란)으로 입력해도 됨
/tmp/kis-open-trading-api/legacy/Sample01/kis_domfuopt.py:65:        "ORD_DVSN_CD": dvsn_cd                  # 주문구분코드 01 : 지정가 02 : 시장가 03 : 조건부 04 : 최유리  10 : 지정가(IOC) .....
/tmp/kis-open-trading-api/legacy/Sample01/kis_domfuopt.py:128:        "NMPR_TYPE_CD": "",                     # 호가유형코드 ※ ORD_DVSN_CD(주문구분코드)를 입력한 경우 ""(공란)으로 입력해도 됨
/tmp/kis-open-trading-api/legacy/Sample01/kis_domfuopt.py:129:        "KRX_NMPR_CNDT_CD": "",                 # 한국거래소호가조건코드 ※ ORD_DVSN_CD(주문구분코드)를 입력한 경우 ""(공란)으로 입력해도 됨
/tmp/kis-open-trading-api/legacy/Sample01/kis_domfuopt.py:132:        "ORD_DVSN_CD": ord_dvsn                 # 주문구분코드 (취소) 01, (정정) 01 : 지정가 02 : 시장가 03 : 조건부 04 : 최유리  10 : 지정가(IOC) .....
/tmp/kis-open-trading-api/legacy/Sample01/kis_domfuopt.py:347:        "ORD_DVSN_CD": ord_dvsn                     # 주문구분코드 01 : 지정가 02 : 시장가 03 : 조건부 04 : 최유리 10 : 지정가(IOC) .....

exec
/bin/zsh -lc 'rg -n "VTTT1006U|VTTT1001U|TTTT1006U|TTTT1001U|해외주식.*매도|미국 매도" /tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json /tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json' in /Users/manager/side/makemoney
exec
/bin/zsh -lc "nl -ba /tmp/kis-open-trading-api/legacy/Sample01/kis_ovrseastk.py | sed -n '45,120p'" in /Users/manager/side/makemoney
exec
/bin/zsh -lc "nl -ba /tmp/kis-open-trading-api/examples_llm/overseas_stock/order/order.py | sed -n '45,175p'" in /Users/manager/side/makemoney
 succeeded in 0ms:
    45	    해외주식 주문 API를 호출하여 DataFrame으로 반환합니다.
    46	    
    47	    Args:
    48	        cano (str): 계좌번호 체계(8-2)의 앞 8자리
    49	        acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
    50	        ovrs_excg_cd (str): NASD : 나스닥 NYSE : 뉴욕 AMEX : 아멕스 SEHK : 홍콩 SHAA : 중국상해 SZAA : 중국심천 TKSE : 일본 HASE : 베트남 하노이 VNSE : 베트남 호치민
    51	        pdno (str): 종목코드
    52	        ord_qty (str): 주문수량 (해외거래소 별 최소 주문수량 및 주문단위 확인 필요)
    53	        ovrs_ord_unpr (str): 1주당 가격 * 시장가의 경우 1주당 가격을 공란으로 비우지 않음 "0"으로 입력
    54	        ord_dv (str): 주문구분 (buy: 매수, sell: 매도)
    55	        ctac_tlno (str): 
    56	        mgco_aptm_odno (str): 
    57	        ord_svr_dvsn_cd (str): "0"(Default)
    58	        ord_dvsn (str): [Header tr_id TTTT1002U(미국 매수 주문)] 00 : 지정가 32 : LOO(장개시지정가) 34 : LOC(장마감지정가) * 모의투자 VTTT1002U(미국 매수 주문)로는 00:지정가만 가능  [Header tr_id TTTT1006U(미국 매도 주문)] 00 : 지정가 31 : MOO(장개시시장가) 32 : LOO(장개시지정가) 33 : MOC(장마감시장가) 34 : LOC(장마감지정가) * 모의투자 VTTT1006U(미국 매도 주문)로는 00:지정가만 가능  [Header tr_id TTTS1001U(홍콩 매도 주문)] 00 : 지정가 50 : 단주지정가 * 모의투자 VTTS1001U(홍콩 매도 주문)로는 00:지정가만 가능  [그외 tr_id] 제거
    59	        env_dv (str): 실전모의구분 (real:실전, demo:모의)
    60	        
    61	    Returns:
    62	        Optional[pd.DataFrame]: 해외주식 주문 데이터
    63	        
    64	    Example:
    65	        >>> df = order(
    66	        ...     cano=trenv.my_acct,
    67	        ...     acnt_prdt_cd=trenv.my_prod,
    68	        ...     ovrs_excg_cd="NASD",
    69	        ...     pdno="AAPL",
    70	        ...     ord_qty="1",
    71	        ...     ovrs_ord_unpr="145.00",
    72	        ...     ord_dv="buy",
    73	        ...     ctac_tlno="",
    74	        ...     mgco_aptm_odno="",
    75	        ...     ord_svr_dvsn_cd="0",
    76	        ...     ord_dvsn="00",
    77	        ...     env_dv="real"
    78	        ... )
    79	        >>> print(df)
    80	    """
    81	    # [필수 파라미터 검증]
    82	    if not cano:
    83	        logger.error("cano is required. (e.g. '810XXXXX')")
    84	        raise ValueError("cano is required. (e.g. '810XXXXX')")
    85	    if not acnt_prdt_cd:
    86	        logger.error("acnt_prdt_cd is required. (e.g. '01')")
    87	        raise ValueError("acnt_prdt_cd is required. (e.g. '01')")
    88	    if not ovrs_excg_cd:
    89	        logger.error("ovrs_excg_cd is required. (e.g. 'NASD')")
    90	        raise ValueError("ovrs_excg_cd is required. (e.g. 'NASD')")
    91	    if not pdno:
    92	        logger.error("pdno is required. (e.g. 'AAPL')")
    93	        raise ValueError("pdno is required. (e.g. 'AAPL')")
    94	    if not ord_qty:
    95	        logger.error("ord_qty is required. (e.g. '1')")
    96	        raise ValueError("ord_qty is required. (e.g. '1')")
    97	    if not ovrs_ord_unpr:
    98	        logger.error("ovrs_ord_unpr is required. (e.g. '145.00')")
    99	        raise ValueError("ovrs_ord_unpr is required. (e.g. '145.00')")
   100	    if not ord_dv:
   101	        logger.error("ord_dv is required. (e.g. 'buy' or 'sell')")
   102	        raise ValueError("ord_dv is required. (e.g. 'buy' or 'sell')")
   103	    if not ord_svr_dvsn_cd:
   104	        logger.error("ord_svr_dvsn_cd is required. (e.g. '0')")
   105	        raise ValueError("ord_svr_dvsn_cd is required. (e.g. '0')")
   106	    if not ord_dvsn:
   107	        logger.error("ord_dvsn is required. (e.g. '00')")
   108	        raise ValueError("ord_dvsn is required. (e.g. '00')")
   109	
   110	    # TR ID 설정 (매수/매도 및 거래소별)
   111	    if ord_dv == "buy":
   112	        if ovrs_excg_cd in ("NASD", "NYSE", "AMEX"):
   113	            tr_id = "TTTT1002U"  # 미국 매수 주문 [모의투자] VTTT1002U
   114	        elif ovrs_excg_cd == "SEHK":
   115	            tr_id = "TTTS1002U"  # 홍콩 매수 주문 [모의투자] VTTS1002U
   116	        elif ovrs_excg_cd == "SHAA":
   117	            tr_id = "TTTS0202U"  # 중국상해 매수 주문 [모의투자] VTTS0202U
   118	        elif ovrs_excg_cd == "SZAA":
   119	            tr_id = "TTTS0305U"  # 중국심천 매수 주문 [모의투자] VTTS0305U
   120	        elif ovrs_excg_cd == "TKSE":
   121	            tr_id = "TTTS0308U"  # 일본 매수 주문 [모의투자] VTTS0308U
   122	        elif ovrs_excg_cd in ("HASE", "VNSE"):
   123	            tr_id = "TTTS0311U"  # 베트남(하노이,호치민) 매수 주문 [모의투자] VTTS0311U
   124	        else:
   125	            logger.error("ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
   126	            raise ValueError("ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
   127	        sll_type = ""
   128	    elif ord_dv == "sell":
   129	        if ovrs_excg_cd in ("NASD", "NYSE", "AMEX"):
   130	            tr_id = "TTTT1006U"  # 미국 매도 주문 [모의투자] VTTT1006U
   131	        elif ovrs_excg_cd == "SEHK":
   132	            tr_id = "TTTS1001U"  # 홍콩 매도 주문 [모의투자] VTTS1001U
   133	        elif ovrs_excg_cd == "SHAA":
   134	            tr_id = "TTTS1005U"  # 중국상해 매도 주문 [모의투자] VTTS1005U
   135	        elif ovrs_excg_cd == "SZAA":
   136	            tr_id = "TTTS0304U"  # 중국심천 매도 주문 [모의투자] VTTS0304U
   137	        elif ovrs_excg_cd == "TKSE":
   138	            tr_id = "TTTS0307U"  # 일본 매도 주문 [모의투자] VTTS0307U
   139	        elif ovrs_excg_cd in ("HASE", "VNSE"):
   140	            tr_id = "TTTS0310U"  # 베트남(하노이,호치민) 매도 주문 [모의투자] VTTS0310U
   141	        else:
   142	            logger.error("ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
   143	            raise ValueError("ovrs_excg_cd is required. (e.g. 'NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE')")
   144	        sll_type = "00"
   145	    else:
   146	        logger.error("ord_dv is required. (e.g. 'buy' or 'sell')")
   147	        raise ValueError("ord_dv is required. (e.g. 'buy' or 'sell')")
   148	
   149	    # 모의투자인 경우 TR ID 앞에 V 붙이기
   150	    if env_dv == "demo":
   151	        tr_id = "V" + tr_id[1:]
   152	    elif env_dv != "real":
   153	        logger.error("env_dv can only be 'real' or 'demo'")
   154	        raise ValueError("env_dv can only be 'real' or 'demo'")
   155	
   156	    params = {
   157	        "CANO": cano,
   158	        "ACNT_PRDT_CD": acnt_prdt_cd,
   159	        "OVRS_EXCG_CD": ovrs_excg_cd,
   160	        "PDNO": pdno,
   161	        "ORD_QTY": ord_qty,
   162	        "OVRS_ORD_UNPR": ovrs_ord_unpr,
   163	        "CTAC_TLNO": ctac_tlno,
   164	        "MGCO_APTM_ODNO": mgco_aptm_odno,
   165	        "SLL_TYPE": sll_type,
   166	        "ORD_SVR_DVSN_CD": ord_svr_dvsn_cd,
   167	        "ORD_DVSN": ord_dvsn,
   168	    }
   169	
   170	    res = ka._url_fetch(api_url=API_URL,
   171	                        ptr_id=tr_id,
   172	                        tr_cont="",
   173	                        params=params,
   174	                        postFlag=True
   175	            )

 succeeded in 0ms:
    45	def get_overseas_order(ord_dv="", excg_cd="", itm_no="", qty=0, unpr=0, tr_cont="", FK100="", NK100="", dataframe=None):  # 국내주식주문 > 주식주문(현금)
    46	    url = '/uapi/overseas-stock/v1/trading/order'
    47	
    48	    if ord_dv == "buy":
    49	        if excg_cd in ("NASD","NYSE","AMEX"):
    50	            tr_id = "TTTT1002U"  # 미국 매수 주문 [모의투자] VTTT1002U
    51	        elif excg_cd == "SHEK":
    52	            tr_id = "TTTS1002U"  # 홍콩 매수 주문 [모의투자] VTTS1002U
    53	        elif excg_cd == "SHAA":
    54	            tr_id = "TTTS0202U"  # 중국상해 매수 주문 [모의투자] VTTS0202U
    55	        elif excg_cd == "SZAA":
    56	            tr_id = "TTTS0305U"  # 중국심천 매수 주문 [모의투자] VTTS0305U
    57	        elif excg_cd == "TKSE":
    58	            tr_id = "TTTS0308U"  # 일본 매수 주문 [모의투자] VTTS0308U
    59	        elif excg_cd in ("HASE", "VNSE"):
    60	            tr_id = "TTTS0311U"  # 베트남(하노이,호치민) 매수 주문 [모의투자] VTTS0311U
    61	        else:
    62	            print("해외거래소코드 확인요망!!!")
    63	            return None
    64	    elif ord_dv == "sell":
    65	        if excg_cd in ("NASD", "NYSE", "AMEX"):
    66	            tr_id = "TTTT1006U"  # 미국 매도 주문 [모의투자] VTTT1006U
    67	        elif excg_cd == "SHEK":
    68	            tr_id = "TTTS1001U"  # 홍콩 매도 주문 [모의투자] VTTS1001U
    69	        elif excg_cd == "SHAA":
    70	            tr_id = "TTTS1005U"  # 중국상해 매도 주문 [모의투자] VTTS1005U
    71	        elif excg_cd == "SZAA":
    72	            tr_id = "TTTS0304U"  # 중국심천 매도 주문 [모의투자] VTTS0304U
    73	        elif excg_cd == "TKSE":
    74	            tr_id = "TTTS0307U"  # 일본 매도 주문 [모의투자] VTTS0307U
    75	        elif excg_cd in ("HASE", "VNSE"):
    76	            tr_id = "TTTS0310U"  # 베트남(하노이,호치민) 매도 주문 [모의투자] VTTS0311U
    77	        else:
    78	            print("해외거래소코드 확인요망!!!")
    79	            return None
    80	    else:
    81	        print("매수/매도 구분 확인요망!")
    82	        return None
    83	
    84	    if itm_no == "":
    85	        print("주문종목번호(상품번호) 확인요망!!!")
    86	        return None
    87	
    88	    if qty == 0:
    89	        print("주문수량 확인요망!!!")
    90	        return None
    91	
    92	    if unpr == 0:
    93	        print("해외주문단가 확인요망!!!")
    94	        return None
    95	
    96	    if ord_dv == "buy":
    97	        sll_type = ""
    98	    elif ord_dv == "sell":
    99	        sll_type = "00"
   100	    else:
   101	        print("매수/매도 구분 확인요망!!!")
   102	        return None
   103	
   104	    params = {
   105	        "CANO": kis.getTREnv().my_acct,         # 종합계좌번호 8자리
   106	        "ACNT_PRDT_CD": kis.getTREnv().my_prod, # 계좌상품코드 2자리
   107	        "OVRS_EXCG_CD": excg_cd,                # 해외거래소코드
   108	                                                # NASD:나스닥,NYSE:뉴욕,AMEX:아멕스,SEHK:홍콩,SHAA:중국상해,SZAA:중국심천,TKSE:일본,HASE:베트남하노이,VNSE:호치민
   109	        "PDNO": itm_no,                         # 종목코드
   110	        "ORD_DVSN": "00",                       # 주문구분 00:지정가, 01:시장가, 02:조건부지정가  나머지주문구분 API 문서 참조
   111	        "ORD_QTY": str(int(qty)),               # 주문주식수
   112	        "OVRS_ORD_UNPR": str(int(unpr)),        # 해외주문단가
   113	        "SLL_TYPE": sll_type,                   # 판매유형
   114	        "ORD_SVR_DVSN_CD": "0"                  # 주문서버구분코드l
   115	    }
   116	
   117	    res = kis._url_fetch(url, tr_id, tr_cont, params, postFlag=True)
   118	    if str(res.getBody().rt_cd) == "0":
   119	        current_data = pd.DataFrame(res.getBody().output, index=[0])
   120	        dataframe = current_data

 succeeded in 0ms:
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3039:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3143:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3247:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3351:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3455:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3559:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3871:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:3975:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4079:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4183:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4287:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문"
/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4392:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문"
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18194:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18301:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18409:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18517:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18625:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:18732:										"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19050:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19154:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19258:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19362:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19466:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19570:										"description": "[실전투자]\nTTTT3016U : 미국 매도 예약 주문\nTTTT3014U : 미국 매수 예약 주문\nTTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문\n\n[모의투자]\nVTTT3016U : 미국 매도 예약 주문\nVTTT3014U : 미국 매수 예약 주문\nVTTS3013U : 중국/홍콩/일본/베트남 예약 매수/매도/취소 주문",
/tmp/kis-open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20482:							"name": "J_해외주식 미국주간주문(매도)",

codex
I found the conflict: the newer Python sample derives paper sell as `VTTT1006U`, but the official Postman sample lists paper US sell as `VTTT1001U`. Your runtime error is consistent with the Python sample being wrong for paper US sell.
exec
/bin/zsh -lc "nl -ba /tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json | sed -n '3105,3175p'" in /Users/manager/side/makemoney
exec
/bin/zsh -lc "nl -ba /tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json | sed -n '3000,3075p'" in /Users/manager/side/makemoney
 succeeded in 0ms:
  3105												"    pm.environment.set(\"VTS_HASH\", res.json().HASH);\r",
  3106												"});"
  3107											],
  3108											"type": "text/javascript"
  3109										}
  3110									}
  3111								],
  3112								"request": {
  3113									"method": "POST",
  3114									"header": [
  3115										{
  3116											"key": "content-type",
  3117											"value": "application/json",
  3118											"type": "text",
  3119											"description": "application/json; charset=utf-8"
  3120										},
  3121										{
  3122											"key": "authorization",
  3123											"value": "Bearer {{VTS_TOKEN}}",
  3124											"type": "text",
  3125											"description": "OAuth 토큰이 필요한 API 경우 발급한 Access token\n일반고객(Access token 유효기간 1일, OAuth 2.0의 Client Credentials Grant 절차를 준용)\n법인(Access token 유효기간 3개월, Refresh token 유효기간 1년, OAuth 2.0의 Authorization Code Grant 절차를 준용)"
  3126										},
  3127										{
  3128											"key": "appkey",
  3129											"value": "{{VTS_APPKEY}}",
  3130											"type": "text",
  3131											"description": "한국투자증권 홈페이지에서 발급받은 appkey (절대 노출되지 않도록 주의해주세요.)"
  3132										},
  3133										{
  3134											"key": "appsecret",
  3135											"value": "{{VTS_APPSECRET}}",
  3136											"type": "text",
  3137											"description": "한국투자증권 홈페이지에서 발급받은 appsecret (절대 노출되지 않도록 주의해주세요.)"
  3138										},
  3139										{
  3140											"key": "tr_id",
  3141											"value": "VTTS0308U",
  3142											"type": "text",
  3143											"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
  3144										},
  3145										{
  3146											"key": "hashkey",
  3147											"value": "{{VTS_HASH}}",
  3148											"type": "default",
  3149											"description": "[POST API 대상] Client가 요청하는 Request Body를 hashkey api로 생성한 Hash값\n* API문서 > hashkey 참조",
  3150											"disabled": true
  3151										}
  3152									],
  3153									"body": {
  3154										"mode": "raw",
  3155										"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"TKSE\",\r\n    \"PDNO\": \"4689\",\r\n    \"ORD_QTY\": \"100\",\r\n    \"OVRS_ORD_UNPR\": \"450.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
  3156										"options": {
  3157											"raw": {
  3158												"language": "json"
  3159											}
  3160										}
  3161									},
  3162									"url": {
  3163										"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
  3164										"host": [
  3165											"{{VTS}}"
  3166										],
  3167										"path": [
  3168											"uapi",
  3169											"overseas-stock",
  3170											"v1",
  3171											"trading",
  3172											"order"
  3173										]
  3174									}
  3175								},

 succeeded in 0ms:
  3000												"    // 환경변수 값 세팅 \r",
  3001												"    pm.environment.set(\"VTS_HASH\", res.json().HASH);\r",
  3002												"});"
  3003											],
  3004											"type": "text/javascript"
  3005										}
  3006									}
  3007								],
  3008								"request": {
  3009									"method": "POST",
  3010									"header": [
  3011										{
  3012											"key": "content-type",
  3013											"value": "application/json",
  3014											"type": "text",
  3015											"description": "application/json; charset=utf-8"
  3016										},
  3017										{
  3018											"key": "authorization",
  3019											"value": "Bearer {{VTS_TOKEN}}",
  3020											"type": "text",
  3021											"description": "OAuth 토큰이 필요한 API 경우 발급한 Access token\n일반고객(Access token 유효기간 1일, OAuth 2.0의 Client Credentials Grant 절차를 준용)\n법인(Access token 유효기간 3개월, Refresh token 유효기간 1년, OAuth 2.0의 Authorization Code Grant 절차를 준용)"
  3022										},
  3023										{
  3024											"key": "appkey",
  3025											"value": "{{VTS_APPKEY}}",
  3026											"type": "text",
  3027											"description": "한국투자증권 홈페이지에서 발급받은 appkey (절대 노출되지 않도록 주의해주세요.)"
  3028										},
  3029										{
  3030											"key": "appsecret",
  3031											"value": "{{VTS_APPSECRET}}",
  3032											"type": "text",
  3033											"description": "한국투자증권 홈페이지에서 발급받은 appsecret (절대 노출되지 않도록 주의해주세요.)"
  3034										},
  3035										{
  3036											"key": "tr_id",
  3037											"value": "VTTT1002U",
  3038											"type": "text",
  3039											"description": "[실전투자]\nTTTT1002U : 미국 매수 주문\nTTTT1006U : 미국 매도 주문\nTTTS0308U : 일본 매수 주문\nTTTS0307U : 일본 매도 주문\nTTTS0202U : 상해 매수 주문\nTTTS1005U : 상해 매도 주문\nTTTS1002U : 홍콩 매수 주문\nTTTS1001U : 홍콩 매도 주문\nTTTS0305U : 심천 매수 주문\nTTTS0304U : 심천 매도 주문\nTTTS0311U : 베트남 매수 주문\nTTTS0310U : 베트남 매도 주문\n\n[모의투자]\nVTTT1002U : 미국 매수 주문\nVTTT1001U : 미국 매도 주문\nVTTS0308U : 일본 매수 주문\nVTTS0307U : 일본 매도 주문\nVTTS0202U : 상해 매수 주문\nVTTS1005U : 상해 매도 주문\nVTTS1002U : 홍콩 매수 주문\nVTTS1001U : 홍콩 매도 주문\nVTTS0305U : 심천 매수 주문\nVTTS0304U : 심천 매도 주문\nVTTS0311U : 베트남 매수 주문\nVTTS0310U : 베트남 매도 주문"
  3040										},
  3041										{
  3042											"key": "hashkey",
  3043											"value": "{{VTS_HASH}}",
  3044											"type": "default",
  3045											"description": "[POST API 대상] Client가 요청하는 Request Body를 hashkey api로 생성한 Hash값\n* API문서 > hashkey 참조",
  3046											"disabled": true
  3047										}
  3048									],
  3049									"body": {
  3050										"mode": "raw",
  3051										"raw": "{\r\n    \"CANO\": \"{{CANO}}\",\r\n    \"ACNT_PRDT_CD\": \"01\",\r\n    \"OVRS_EXCG_CD\": \"NASD\",\r\n    \"PDNO\": \"TSLA\",\r\n    \"ORD_QTY\": \"1\",\r\n    \"OVRS_ORD_UNPR\": \"900.0\",\r\n    \"ORD_SVR_DVSN_CD\": \"0\",\r\n    \"ORD_DVSN\": \"00\"\r\n}",
  3052										"options": {
  3053											"raw": {
  3054												"language": "json"
  3055											}
  3056										}
  3057									},
  3058									"url": {
  3059										"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/order",
  3060										"host": [
  3061											"{{VTS}}"
  3062										],
  3063										"path": [
  3064											"uapi",
  3065											"overseas-stock",
  3066											"v1",
  3067											"trading",
  3068											"order"
  3069										]
  3070									}
  3071								},
  3072								"response": []
  3073							},
  3074							{
  3075								"name": "V_해외주식 주문(일본)",

exec
/bin/zsh -lc "python3 - <<'PY'
import json
p='/tmp/kis-open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json'
d=json.load(open(p))

def walk(items, path=''):
    for it in items:
        name=it.get('name','')
        if 'item' in it: yield from walk(it['item'], path+'/'+name)
        else:
            s=json.dumps(it, ensure_ascii=False)
            if 'VTTT1001U' in s or '미국' in name and ('매도' in name or '주문' in name):
                print('---', path+'/'+name)
                req=it.get('request',{})
                print('method', req.get('method'))
                print('url', req.get('url',{}).get('raw'))
                for h in req.get('header',[]):
                    if h.get('key')=='tr_id': print('tr_id header', h)
                body=req.get('body',{}).get('raw')
                if body: print(body[:500])
walk(d['item'])
PY" in /Users/manager/side/makemoney
 succeeded in 0ms:
web search: 
web search: "VTTT1001U"
web search: 
web search: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/order/order.py
web search: 
web search: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/order/order.py
codex
Correct working call for KIS overseas **paper US sell** is:

`tr_id: VTTT1001U`

not `VTTT1006U`.

Known US order `tr_id`s:

| Use | Real | Paper |
|---|---:|---:|
| US buy | `TTTT1002U` | `VTTT1002U` |
| US sell | `TTTT1006U` | `VTTT1001U` |
| US revise/cancel | `TTTT1004U` | `VTTT1004U` |
| US reserve buy | `TTTT3014U` | `VTTT3014U` |
| US reserve sell | `TTTT3016U` | `VTTT3016U` |

`VTTT1006U` is the misleading one: newer KIS Python sample derives it by prefixing real US sell `TTTT1006U` with `V`, but the official KIS Postman sample lists paper US sell as `VTTT1001U`; your error confirms `VTTT1006U` is not accepted in VTS paper for this job. KIS sample repo: [Python sample shows the bad derivation](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/overseas_stock/order/order.py), while [official Postman sample lists `VTTT1001U`](https://github.com/koreainvestment/open-trading-api/blob/main/legacy/postman/%EB%AA%A8%EC%9D%98%EA%B3%84%EC%A2%8C_POSTMAN_%EC%83%98%ED%94%8C%EC%BD%94%EB%93%9C_v1.6.json). A separate summary of KIS API ids also lists paper US sell as `VTTT1001U` and paper US buy as `VTTT1002U`.

Use the same endpoint:

`POST https://openapivts.koreainvestment.com:29443/uapi/overseas-stock/v1/trading/order`

Headers:

```http
content-type: application/json
authorization: Bearer {ACCESS_TOKEN}
appkey: {PAPER_APPKEY}
appsecret: {PAPER_APPSECRET}
tr_id: VTTT1001U
custtype: P
```

Body for selling 1 AAPL limit:

```json
{
  "CANO": "12345678",
  "ACNT_PRDT_CD": "01",
  "OVRS_EXCG_CD": "NASD",
  "PDNO": "AAPL",
  "ORD_QTY": "1",
  "OVRS_ORD_UNPR": "195.00",
  "SLL_TYPE": "00",
  "ORD_SVR_DVSN_CD": "0",
  "ORD_DVSN": "00"
}
```

For paper US, use `ORD_DVSN: "00"` limit. Do not use US daytime order for paper; KIS lists daytime overseas stock paper trading as unsupported. To flatten in paper, submit normal-session sell with `VTTT1001U`, or after hours place a reserve sell with `VTTT3016U` on `/uapi/overseas-stock/v1/trading/order-resv`.
tokens used
141,807

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
