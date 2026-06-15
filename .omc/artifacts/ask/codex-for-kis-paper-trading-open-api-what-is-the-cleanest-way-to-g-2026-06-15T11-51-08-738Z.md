# codex advisor artifact

- Provider: codex
- Exit code: 0
- Created at: 2026-06-15T11:51:08.740Z

## Original task

For KIS (한국투자증권) paper trading Open API, what is the cleanest way to get a live USD/KRW exchange rate to convert overseas positions to KRW base? Options I know: (a) the overseas balance inquiry response (VTTS3012R, /uapi/overseas-stock/v1/trading/inquire-balance) — does its output include an FX rate field (e.g. frst_bltn_exrt or bass_exrt)? what's the exact field name? (b) overseas present-balance VTRP6504R output3? (c) a dedicated FX endpoint? 

Recommend the simplest reliable source already reachable with the account creds (prefer reusing the balance call we already make). Give the exact response field name and a fallback (e.g. config default) if the field is empty. Terse, cite KIS field names precisely. If unsure on exact field name, say so and give the most likely candidates from the KIS overseas balance schema.

## Final prompt

For KIS (한국투자증권) paper trading Open API, what is the cleanest way to get a live USD/KRW exchange rate to convert overseas positions to KRW base? Options I know: (a) the overseas balance inquiry response (VTTS3012R, /uapi/overseas-stock/v1/trading/inquire-balance) — does its output include an FX rate field (e.g. frst_bltn_exrt or bass_exrt)? what's the exact field name? (b) overseas present-balance VTRP6504R output3? (c) a dedicated FX endpoint? 

Recommend the simplest reliable source already reachable with the account creds (prefer reusing the balance call we already make). Give the exact response field name and a fallback (e.g. config default) if the field is empty. Terse, cite KIS field names precisely. If unsure on exact field name, say so and give the most likely candidates from the KIS overseas balance schema.

## Raw output

```text
Use **`VTRP6504R` present-balance**, not `VTTS3012R`.

- `VTTS3012R` `/uapi/overseas-stock/v1/trading/inquire-balance`: I do **not** see FX fields in the official sample schema. No `frst_bltn_exrt`, no `bass_exrt`.
- `VTRP6504R` `/uapi/overseas-stock/v1/trading/inquire-present-balance`: has the FX fields.
  - Per-position: `output1[].bass_exrt` = `기준환율`
  - Per-currency/cash: `output2[].frst_bltn_exrt` = `최초고시환율`
  - `output3` is summary totals, not the FX source.

Recommendation: if you already need KRW-base overseas valuation, call `inquire-present-balance` with `WCRC_FRCR_DVSN_CD=01`, `NATN_CD=000`, `TR_MKET_CD=00`, `INQR_DVSN_CD=00`, then use:

```text
USD/KRW = output1 row where crcy_cd/buy_crcy_cd == "USD" -> bass_exrt
fallback = output2 row where crcy_cd == "USD" -> frst_bltn_exrt
fallback = config default, e.g. DEFAULT_USD_KRW
```

Dedicated FX fallback exists via overseas quotation chart APIs, e.g. `inquire-daily-chartprice` with `FID_COND_MRKT_DIV_CODE=X`, but it is less clean for account valuation than `VTRP6504R`.

Sources: KIS official GitHub samples for `inquire_balance` and `inquire_present_balance`, plus KIS portal listing for overseas quotation FX period APIs.


OpenAI Codex v0.139.0
--------
workdir: /Users/manager/side/makemoney
model: gpt-5.5
provider: openai
approval: never
sandbox: danger-full-access
reasoning effort: none
reasoning summaries: none
session id: 019ecb1d-19b9-7692-bd97-f405c981d042
--------
user
For KIS (한국투자증권) paper trading Open API, what is the cleanest way to get a live USD/KRW exchange rate to convert overseas positions to KRW base? Options I know: (a) the overseas balance inquiry response (VTTS3012R, /uapi/overseas-stock/v1/trading/inquire-balance) — does its output include an FX rate field (e.g. frst_bltn_exrt or bass_exrt)? what's the exact field name? (b) overseas present-balance VTRP6504R output3? (c) a dedicated FX endpoint? 

Recommend the simplest reliable source already reachable with the account creds (prefer reusing the balance call we already make). Give the exact response field name and a fallback (e.g. config default) if the field is empty. Terse, cite KIS field names precisely. If unsure on exact field name, say so and give the most likely candidates from the KIS overseas balance schema.
codex
I’ll verify against KIS’s current API docs/schema rather than relying on memory, because the exact field names are the important part here.
web search: 
web search: KIS Open API VTTS3012R inquire-balance frst_bltn_exrt bass_exrt
web search: 
web search: github koreainvestment open-trading-api VTTS3012R
codex
The official KIS GitHub is accessible and looks newer than many blog mirrors, so I’m checking its generated examples plus portal schema references for `VTTS3012R` and `VTRP6504R`.
exec
/bin/zsh -lc 'rg -n "VTTS3012R|VTRP6504R|frst_bltn_exrt|bass_exrt|inquire-balance|present-balance" .' in /Users/manager/side/makemoney
 succeeded in 0ms:
./trader/execution/kis_client.py:425:        """GET /uapi/domestic-stock/v1/trading/inquire-balance (VTTC8434R paper).
./trader/execution/kis_client.py:438:            "/uapi/domestic-stock/v1/trading/inquire-balance",
./trader/execution/kis_client.py:463:        """GET /uapi/overseas-stock/v1/trading/inquire-balance (VTTS3012R paper).
./trader/execution/kis_client.py:477:            "/uapi/overseas-stock/v1/trading/inquire-balance",
./trader/execution/kis_client.py:478:            headers=self._headers("VTTS3012R"),
./tests/test_kis_balance.py:54:    if "inquire-balance" in p and "domestic-stock" in p:
./tests/test_kis_balance.py:56:    if "inquire-balance" in p and "overseas-stock" in p:

exec
/bin/zsh -lc 'curl -L https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/kis_devlp.yaml | rg -n "VTTS3012R|VTRP6504R|frst_bltn_exrt|bass_exrt|inquire-balance|present-balance" -C 3' in /Users/manager/side/makemoney
 exited 1 in 248ms:
100  1218  100  1218    0     0   4722      0 --:--:-- --:--:-- --:--:--  4739

exec
/bin/zsh -lc 'curl -s https://api.github.com/search/code?q=VTTS3012R+repo:koreainvestment/open-trading-api' in /Users/manager/side/makemoney
 exited 1 in 0ms:
zsh:1: no matches found: https://api.github.com/search/code?q=VTTS3012R+repo:koreainvestment/open-trading-api

exec
/bin/zsh -lc "curl -s 'https://api.github.com/search/code?q=VTTS3012R+repo:koreainvestment/open-trading-api'" in /Users/manager/side/makemoney
 succeeded in 200ms:
{
  "message": "Requires authentication",
  "documentation_url": "https://docs.github.com/rest",
  "status": "401"
}
codex
The local repo already has a KIS client using `VTTS3012R`, but no schema constants. I’m pulling the official sample repository into a temp path so I can grep the actual sample files without touching your project.
exec
/bin/zsh -lc 'tmpdir=$(mktemp -d) && git clone --depth 1 https://github.com/koreainvestment/open-trading-api.git "$tmpdir/open-trading-api" >/dev/null 2>&1 && rg -n "VTTS3012R|VTRP6504R|frst_bltn_exrt|bass_exrt|inquire-balance|present-balance" "$tmpdir/open-trading-api"' in /Users/manager/side/makemoney
 succeeded in 4250ms:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/rest/kis_api.py:271:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:402:            string url = "/uapi/overseas-stock/v1/trading/inquire-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:403:            string trID = "TTTS3012R"; // 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:435:            string url = "/uapi/overseas-stock/v1/trading/inquire-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:436:            string trID = "TTTS3012R"; // 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:633:            string url = "/uapi/overseas-stock/v1/trading/inquire-present-balance";
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample02/CSharp/KIS_OverseaStk.cs:634:            string trID = "CTRP6504R"; // 모의투자 VTRP6504R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3730:    api_url = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:3882:    api_url = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11370:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_stock/domestic_stock_functions.py:11638:    api_url = "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1056:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=00&CTX_AREA_FK100&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1065:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1778:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/pension/inquire-present-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=29&USER_DVSN_CD=00&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:1788:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2256:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/pension/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=29&ACCA_DVSN_CD=00&INQR_DVSN=00&CTX_AREA_FK100&CTX_AREA_NK100",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2266:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2342:									"raw": "{{PROD}}/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=02&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=01&COST_ICLD_YN=N&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:2351:										"inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16072:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=01&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16081:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16725:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&INQR_DT=20230906&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16734:										"inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16942:									"raw": "{{PROD}}/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl?CANO={{CANO_REAL_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=02&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:16951:										"inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19858:										"description": "[실전투자]\nTTTS3012R\n\n[모의투자]\nVTTS3012R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19867:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=NASD&TR_CRCY_CD=USD&CTX_AREA_FK200=&CTX_AREA_NK200",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:19876:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20102:										"description": "[실전투자]\nCTRP6504R\n\n[모의투자]\nVTRP6504R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20111:									"raw": "{{PROD}}/uapi/overseas-stock/v1/trading/inquire-present-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&NATN_CD=000&WCRC_FRCR_DVSN_CD=01&TR_MKET_CD=00&INQR_DVSN_CD=00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:20120:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25929:									"raw": "{{PROD}}/uapi/domestic-bond/v1/trading/inquire-balance?CANO={{CANO_REAL}}&ACNT_PRDT_CD=01&INQR_CNDT=00&PDNO=&BUY_DT=&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/실전계좌_POSTMAN_샘플코드_v2.6.json:25938:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1396:      "api_path": "/uapi/overseas-stock/v1/trading/inquire-present-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json:1496:      "api_path": "/uapi/overseas-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:277:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1010:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_futureoption.json:1100:      "api_path": "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:2694:      "api_path": "/uapi/domestic-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3160:      "api_path": "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:3675:      "api_path": "/uapi/domestic-stock/v1/trading/pension/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_stock.json:4446:      "api_path": "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/domestic_bond.json:593:      "api_path": "/uapi/domestic-bond/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:638:        tr_id = "VTTS3012R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:642:    api_url = "/uapi/overseas-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1679:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/overseas_stock/overseas_stock_functions.py:1683:    api_url = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_bond/domestic_bond_functions.py:430:    api_url = "/uapi/domestic-bond/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:468:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:576:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_user/domestic_futureoption/domestic_futureoption_functions.py:688:    api_url = "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1919:									"raw": "{{VTS}}/uapi/domestic-stock/v1/trading/inquire-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&AFHR_FLPR_YN=N&OFL_YN=&INQR_DVSN=01&UNPR_DVSN=01&FUND_STTL_ICLD_YN=N&FNCG_AMT_AUTO_RDPT_YN=N&PRCS_DVSN=00&CTX_AREA_FK100=&CTX_AREA_NK100=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:1928:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2545:									"raw": "{{VTS}}/uapi/domestic-futureoption/v1/trading/inquire-balance?CANO={{CANO_T}}&ACNT_PRDT_CD=03&MGNA_DVSN=01&EXCC_STAT_CD=1&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:2554:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4678:										"value": "VTTS3012R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4680:										"description": "[실전투자]\nTTTS3012R\n\n[모의투자]\nVTTS3012R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4688:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&OVRS_EXCG_CD=TKSE&TR_CRCY_CD=JPY&CTX_AREA_FK200=&CTX_AREA_NK200=",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4697:										"inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4922:										"value": "VTRP6504R",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4924:										"description": "[실전투자]\nCTRP6504R\n\n[모의투자]\nVTRP6504R"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4932:									"raw": "{{VTS}}/uapi/overseas-stock/v1/trading/inquire-present-balance?CANO={{CANO}}&ACNT_PRDT_CD=01&NATN_CD=000&WCRC_FRCR_DVSN_CD=01&TR_MKET_CD=00&INQR_DVSN_CD=00",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/postman/모의계좌_POSTMAN_샘플코드_v1.6.json:4941:										"inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_domstk.py:293:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_domstk.py:324:    url = '/uapi/domestic-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_domstk.py:629:    url = '/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_domstk.py:660:    url = '/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_ovrseastk.py:353:    url = '/uapi/overseas-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_ovrseastk.py:354:    tr_id = "TTTS3012R"   # 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_ovrseastk.py:398:    url = '/uapi/overseas-stock/v1/trading/inquire-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_ovrseastk.py:399:    tr_id = "TTTS3012R"   # 모의투자 VTTS3012R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_ovrseastk.py:575:    url = '/uapi/overseas-stock/v1/trading/inquire-present-balance'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/legacy/Sample01/kis_ovrseastk.py:576:    tr_id = "CTRP6504R"   # 모의투자 VTRP6504R
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2719:    'usd_frst_bltn_exrt': '미국달러최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2720:    'hkd_frst_bltn_exrt': '홍콩달러최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2721:    'jpy_frst_bltn_exrt': '일본엔화최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2722:    'cny_frst_bltn_exrt': '중국위안화최초고시환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10745:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10766:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10869:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11123:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11141:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11352:    'bass_exrt': '기준환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/backtester/kis_backtest/providers/kis/brokerage.py:201:        API: /uapi/domestic-stock/v1/trading/inquire-balance
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/backtester/kis_backtest/providers/kis/constants.py:75:    DOMESTIC_BALANCE = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py:38:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py:52:    'stck_sll_tlex', 'ovrs_rlzt_pfls_amt', 'pftrt', 'exrt', 'frst_bltn_exrt',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:35:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:53:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/foreign_margin/chk_foreign_margin.py:34:    'bass_exrt': '기준환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:36:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:57:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:91:    'frcr_pchs_amt', 'frcr_evlu_amt2', 'evlu_pfls_amt2', 'evlu_pfls_rt1', 'bass_exrt',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:94:    'frst_bltn_exrt', 'frcr_buy_mgn_amt', 'frcr_etc_mgna', 'frcr_drwg_psbl_amt_1', 'frcr_evlu_amt2',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:26:API_URL = "/uapi/overseas-stock/v1/trading/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py:108:        tr_id = "VTRP6504R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_bond/inquire_balance/inquire_balance.py:28:API_URL = "/uapi/domestic-bond/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:25:API_URL = "/uapi/overseas-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_balance/inquire_balance.py:98:        tr_id = "VTTS3012R"  # 모의투자용 TR ID
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/strategy_builder/core/data_fetcher.py:69:        "/uapi/domestic-stock/v1/trading/inquire-balance",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/inquire_balance_rlz_pl/inquire_balance_rlz_pl.py:24:API_URL = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/pension_inquire_present_balance/pension_inquire_present_balance.py:22:API_URL = "/uapi/domestic-stock/v1/trading/pension/inquire-present-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/inquire_balance/inquire_balance.py:24:API_URL = "/uapi/domestic-stock/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/intgr_margin/chk_intgr_margin.py:122:    'usd_frst_bltn_exrt': '미국달러최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/intgr_margin/chk_intgr_margin.py:123:    'hkd_frst_bltn_exrt': '홍콩달러최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/intgr_margin/chk_intgr_margin.py:124:    'jpy_frst_bltn_exrt': '일본엔화최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/intgr_margin/chk_intgr_margin.py:125:    'cny_frst_bltn_exrt': '중국위안화최초고시환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_stock/pension_inquire_balance/pension_inquire_balance.py:24:API_URL = "/uapi/domestic-stock/v1/trading/pension/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_valuation_pl/inquire_balance_valuation_pl.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_futureoption/inquire_balance/inquire_balance.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/domestic_futureoption/inquire_balance_settlement_pl/inquire_balance_settlement_pl.py:23:API_URL = "/uapi/domestic-futureoption/v1/trading/inquire-balance-settlement-pl"

exec
/bin/zsh -lc "sed -n '1,150p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
"""
Created on 2025-06-30

"""

import sys
import logging

import pandas as pd

sys.path.extend(['../..', '.'])  # kis_auth 파일 경로 추가
import kis_auth as ka
from inquire_balance import inquire_balance

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 잔고 [v1_해외주식-006]
##############################################################################################

COLUMN_MAPPING = {
    'cano': '종합계좌번호',
    'acnt_prdt_cd': '계좌상품코드',
    'prdt_type_cd': '상품유형코드',
    'ovrs_pdno': '해외상품번호',
    'frcr_evlu_pfls_amt': '외화평가손익금액',
    'evlu_pfls_rt': '평가손익율',
    'pchs_avg_pric': '매입평균가격',
    'ovrs_cblc_qty': '해외잔고수량',
    'ord_psbl_qty': '주문가능수량',
    'frcr_pchs_amt1': '외화매입금액1',
    'ovrs_stck_evlu_amt': '해외주식평가금액',
    'now_pric2': '현재가격2',
    'tr_crcy_cd': '거래통화코드',
    'ovrs_excg_cd': '해외거래소코드',
    'loan_type_cd': '대출유형코드',
    'loan_dt': '대출일자',
    'expd_dt': '만기일자',
    'frcr_pchs_amt1': '외화매입금액1',
    'ovrs_rlzt_pfls_amt': '해외실현손익금액',
    'ovrs_tot_pfls': '해외총손익',
    'rlzt_erng_rt': '실현수익율',
    'tot_evlu_pfls_amt': '총평가손익금액',
    'tot_pftrt': '총수익률',
    'frcr_buy_amt_smtl1': '외화매수금액합계1',
    'ovrs_rlzt_pfls_amt2': '해외실현손익금액2',
    'frcr_buy_amt_smtl2': '외화매수금액합계2'
}

# 숫자형 컬럼 정의
NUMERIC_COLUMNS = []

def main():
    """
    [해외주식] 주문/계좌
    해외주식 잔고[해외주식-006]

    해외주식 잔고 테스트 함수
    
    Parameters:
        - cano (str): 종합계좌번호 ()
        - acnt_prdt_cd (str): 계좌상품코드 ()
        - ovrs_excg_cd (str): 해외거래소코드 ()
        - tr_crcy_cd (str): 거래통화코드 ()
        - FK200 (str): 연속조회검색조건200 ()
        - NK200 (str): 연속조회키200 ()

    Returns:
        - DataFrame: 해외주식 잔고 결과
    
    Example:
        >>> df = inquire_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, ovrs_excg_cd="NASD", tr_crcy_cd="USD")
    """
    try:
        # pandas 출력 옵션 설정
        pd.set_option('display.max_columns', None)  # 모든 컬럼 표시
        pd.set_option('display.width', None)  # 출력 너비 제한 해제
        pd.set_option('display.max_rows', None)  # 모든 행 표시

        # 토큰 발급
        logger.info("토큰 발급 중...")
        ka.auth()
        logger.info("토큰 발급 완료")
        trenv = ka.getTREnv()

        # API 호출
        logger.info("API 호출")
        result1, result2 = inquire_balance(
            cano=trenv.my_acct,  # 종합계좌번호
            acnt_prdt_cd=trenv.my_prod,  # 계좌상품코드
            ovrs_excg_cd="NASD",  # 해외거래소코드
            tr_crcy_cd="USD",  # 거래통화코드
            FK200="",  # 연속조회검색조건200
            NK200="",  # 연속조회키200
        )
        
        # output1 결과 처리
        logging.info("=== output1 결과 ===")
        logging.info("사용 가능한 컬럼: %s", result1.columns.tolist())
        
        # 한글 컬럼명으로 변환
        result1 = result1.rename(columns=COLUMN_MAPPING)
        
        # 숫자형 컬럼 소수점 둘째자리까지 표시
        for col in NUMERIC_COLUMNS:
            if col in result1.columns:
                result1[col] = pd.to_numeric(result1[col], errors='coerce').round(2)
        
        logging.info("결과:")
        print(result1)
        
        # output3 결과 처리
        logging.info("=== output2 결과 ===")
        logging.info("사용 가능한 컬럼: %s", result2.columns.tolist())
        
        # 한글 컬럼명으로 변환
        result2 = result2.rename(columns=COLUMN_MAPPING)
        
        # 숫자형 컬럼 소수점 둘째자리까지 표시
        for col in NUMERIC_COLUMNS:
            if col in result2.columns:
                result2[col] = pd.to_numeric(result2[col], errors='coerce').round(2)
        
        logging.info("결과(output2):")
        print(result2)
        
    except Exception as e:
        logger.error("에러 발생: %s", str(e))
        raise

if __name__ == "__main__":
    main()

exec
/bin/zsh -lc "sed -n '1480,1585p' '/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json' && sed -n '1385,1475p' '/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/Kis Trading MCP/configs/overseas_stock.json'" in /Users/manager/side/makemoney
 succeeded in 0ms:
          "description": "현재 재귀 깊이"
        },
        "max_depth": {
          "name": "max_depth",
          "type": "int",
          "required": true,
          "default_value": 10,
          "description": "최대 재귀 깊이 (기본값: 10)"
        }
      }
    },
    "inquire_balance": {
      "category": "[해외주식] 주문/계좌",
      "name": "해외주식 잔고",
      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance",
      "method": "inquire_balance",
      "api_path": "/uapi/overseas-stock/v1/trading/inquire-balance",
      "params": {
        "cano": {
          "name": "cano",
          "type": "str",
          "required": false,
          "default_value": null,
          "description": "계좌번호 (시스템 자동 설정, 제공 불필요)"
        },
        "acnt_prdt_cd": {
          "name": "acnt_prdt_cd",
          "type": "str",
          "required": false,
          "default_value": null,
          "description": "계좌상품코드 (시스템 자동 설정, 제공 불필요)"
        },
        "ovrs_excg_cd": {
          "name": "ovrs_excg_cd",
          "type": "str",
          "required": true,
          "default_value": null,
          "description": "[모의] NASD : 나스닥 NYSE : 뉴욕  AMEX : 아멕스  [실전] NASD : 미국전체 NAS : 나스닥 NYSE : 뉴욕  AMEX : 아멕스  [모의/실전 공통] SEHK : 홍콩 SHAA : 중국상해 SZAA : 중국심천 TKSE : 일본 HASE : 베트남 하노이 VNSE : 베트남 호치민"
        },
        "tr_crcy_cd": {
          "name": "tr_crcy_cd",
          "type": "str",
          "required": true,
          "default_value": null,
          "description": "USD : 미국달러 HKD : 홍콩달러 CNY : 중국위안화 JPY : 일본엔화 VND : 베트남동"
        },
        "env_dv": {
          "name": "env_dv",
          "type": "str",
          "required": true,
          "default_value": "real"
        },
        "dataframe1": {
          "name": "dataframe1",
          "type": "pd.DataFrame",
          "required": false,
          "default_value": null
        },
        "dataframe2": {
          "name": "dataframe2",
          "type": "pd.DataFrame",
          "required": false,
          "default_value": null
        },
        "tr_cont": {
          "name": "tr_cont",
          "type": "str",
          "required": true,
          "default_value": ""
        },
        "depth": {
          "name": "depth",
          "type": "int",
          "required": true,
          "default_value": 0
        },
        "max_depth": {
          "name": "max_depth",
          "type": "int",
          "required": true,
          "default_value": 10
        }
      }
    },
    "inquire_nccs": {
      "category": "[해외주식] 주문/계좌",
      "name": "해외주식 미체결내역",
      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_nccs",
      "method": "inquire_nccs",
      "api_path": "/uapi/overseas-stock/v1/trading/inquire-nccs",
      "params": {
        "cano": {
          "name": "cano",
          "type": "str",
          "required": false,
          "default_value": null,
          "description": "계좌번호 (시스템 자동 설정, 제공 불필요)"
        },
        "acnt_prdt_cd": {
          "name": "acnt_prdt_cd",
          "type": "str",
          "required": false,
          "default_value": null,
          "description": "계좌상품코드 (시스템 자동 설정, 제공 불필요)"
        },
        "ovrs_excg_cd": {
          "type": "int",
          "required": true,
          "default_value": 10
        }
      }
    },
    "inquire_present_balance": {
      "category": "[해외주식] 주문/계좌",
      "name": "해외주식 체결기준현재잔고",
      "github_url": "https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance",
      "method": "inquire_present_balance",
      "api_path": "/uapi/overseas-stock/v1/trading/inquire-present-balance",
      "params": {
        "cano": {
          "name": "cano",
          "type": "str",
          "required": false,
          "default_value": null,
          "description": "계좌번호 (시스템 자동 설정, 제공 불필요)"
        },
        "acnt_prdt_cd": {
          "name": "acnt_prdt_cd",
          "type": "str",
          "required": false,
          "default_value": null,
          "description": "계좌상품코드 (시스템 자동 설정, 제공 불필요)"
        },
        "wcrc_frcr_dvsn_cd": {
          "name": "wcrc_frcr_dvsn_cd",
          "type": "str",
          "required": true,
          "default_value": null,
          "description": "01 : 원화  02 : 외화"
        },
        "natn_cd": {
          "name": "natn_cd",
          "type": "str",
          "required": true,
          "default_value": null,
          "description": "000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남"
        },
        "tr_mket_cd": {
          "name": "tr_mket_cd",
          "type": "str",
          "required": true,
          "default_value": null,
          "description": "[Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD"
        },
        "inqr_dvsn_cd": {
          "name": "inqr_dvsn_cd",
          "type": "str",
          "required": true,
          "default_value": null,
          "description": "00 : 전체  01 : 일반해외주식  02 : 미니스탁"
        },
        "env_dv": {
          "name": "env_dv",
          "type": "str",
          "required": true,
          "default_value": "real",
          "description": "실전모의구분 (real:실전, demo:모의)"
        },
        "dataframe1": {
          "name": "dataframe1",
          "type": "pd.DataFrame",
          "required": false,
          "default_value": null,
          "description": "누적 데이터프레임 (output1)"
        },
        "dataframe2": {
          "name": "dataframe2",
          "type": "pd.DataFrame",
          "required": false,
          "default_value": null,
          "description": "누적 데이터프레임 (output2)"
        },
        "dataframe3": {
          "name": "dataframe3",
          "type": "pd.DataFrame",
          "required": false,
          "default_value": null,
          "description": "누적 데이터프레임 (output3)"
        },
        "tr_cont": {
          "name": "tr_cont",
          "type": "str",
          "required": true,
          "default_value": "",
          "description": "연속 거래 여부"
        },
        "depth": {

exec
/bin/zsh -lc "sed -n '1,140p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py && sed -n '1,150p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
# -*- coding: utf-8 -*-
"""
Created on 2025-06-30

"""

import sys
import logging

import pandas as pd

sys.path.extend(['../..', '.'])  # kis_auth 파일 경로 추가
import kis_auth as ka
from inquire_present_balance import inquire_present_balance

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 체결기준현재잔고 [v1_해외주식-008]
##############################################################################################

# 컬럼명 매핑 (한글 변환용)
COLUMN_MAPPING = {
    'cblc_qty13': '잔고수량13',
    'thdt_buy_ccld_qty1': '당일매수체결수량1',
    'thdt_sll_ccld_qty1': '당일매도체결수량1',
    'ccld_qty_smtl1': '체결수량합계1',
    'ord_psbl_qty1': '주문가능수량1',
    'frcr_pchs_amt': '외화매입금액',
    'frcr_evlu_amt2': '외화평가금액2',
    'evlu_pfls_amt2': '평가손익금액2',
    'evlu_pfls_rt1': '평가손익율1',
    'pdno': '상품번호',
    'bass_exrt': '기준환율',
    'buy_crcy_cd': '매수통화코드',
    'ovrs_now_pric1': '해외현재가격1',
    'avg_unpr3': '평균단가3',
    'tr_mket_name': '거래시장명',
    'natn_kor_name': '국가한글명',
    'pchs_rmnd_wcrc_amt': '매입잔액원화금액',
    'thdt_buy_ccld_frcr_amt': '당일매수체결외화금액',
    'thdt_sll_ccld_frcr_amt': '당일매도체결외화금액',
    'unit_amt': '단위금액',
    'std_pdno': '표준상품번호',
    'prdt_type_cd': '상품유형코드',
    'loan_rmnd': '대출잔액',
    'loan_dt': '대출일자',
    'loan_expd_dt': '대출만기일자',
    'ovrs_excg_cd': '해외거래소코드',
    'item_lnkg_excg_cd': '종목연동거래소코드',
    'crcy_cd': '통화코드',
    'frcr_buy_amt_smtl': '외화매수금액합계',
    'frcr_sll_amt_smtl': '외화매도금액합계',
    'frcr_dncl_amt_2': '외화예수금액2',
    'frst_bltn_exrt': '최초고시환율',
    'frcr_buy_mgn_amt': '외화매수증거금액',
    'frcr_etc_mgna': '외화기타증거금',
    'frcr_drwg_psbl_amt_1': '외화출금가능금액1',
    'frcr_evlu_amt2': '출금가능원화금액',
    'acpl_cstd_crcy_yn': '현지보관통화여부',
    'nxdy_frcr_drwg_psbl_amt': '익일외화출금가능금액',
    'output3': '응답상세3',
    'pchs_amt_smtl': '매입금액합계',
    'evlu_amt_smtl': '평가금액합계',
    'evlu_pfls_amt_smtl': '평가손익금액합계',
    'dncl_amt': '예수금액',
    'cma_evlu_amt': 'CMA평가금액',
    'tot_dncl_amt': '총예수금액',
    'etc_mgna': '기타증거금',
    'wdrw_psbl_tot_amt': '인출가능총금액',
    'frcr_evlu_tota': '외화평가총액',
    'evlu_erng_rt1': '평가수익율1',
    'pchs_amt_smtl_amt': '매입금액합계금액',
    'evlu_amt_smtl_amt': '평가금액합계금액',
    'tot_evlu_pfls_amt': '총평가손익금액',
    'tot_asst_amt': '총자산금액',
    'buy_mgn_amt': '매수증거금액',
    'mgna_tota': '증거금총액',
    'frcr_use_psbl_amt': '외화사용가능금액',
    'ustl_sll_amt_smtl': '미결제매도금액합계',
    'ustl_buy_amt_smtl': '미결제매수금액합계',
    'tot_frcr_cblc_smtl': '총외화잔고합계',
    'tot_loan_amt': '총대출금액'
}

# 숫자형 컬럼 정의 (소수점 처리용)
NUMERIC_COLUMNS = [
    'cblc_qty13', 'thdt_buy_ccld_qty1', 'thdt_sll_ccld_qty1', 'ccld_qty_smtl1', 'ord_psbl_qty1',
    'frcr_pchs_amt', 'frcr_evlu_amt2', 'evlu_pfls_amt2', 'evlu_pfls_rt1', 'bass_exrt',
    'ovrs_now_pric1', 'avg_unpr3', 'pchs_rmnd_wcrc_amt', 'thdt_buy_ccld_frcr_amt', 'thdt_sll_ccld_frcr_amt',
    'unit_amt', 'loan_rmnd', 'frcr_buy_amt_smtl', 'frcr_sll_amt_smtl', 'frcr_dncl_amt_2',
    'frst_bltn_exrt', 'frcr_buy_mgn_amt', 'frcr_etc_mgna', 'frcr_drwg_psbl_amt_1', 'frcr_evlu_amt2',
    'nxdy_frcr_drwg_psbl_amt', 'pchs_amt_smtl', 'evlu_amt_smtl', 'evlu_pfls_amt_smtl', 'dncl_amt',
    'cma_evlu_amt', 'tot_dncl_amt', 'etc_mgna', 'wdrw_psbl_tot_amt', 'frcr_evlu_tota',
    'evlu_erng_rt1', 'pchs_amt_smtl_amt', 'evlu_amt_smtl_amt', 'tot_evlu_pfls_amt', 'tot_asst_amt',
    'buy_mgn_amt', 'mgna_tota', 'frcr_use_psbl_amt', 'ustl_sll_amt_smtl', 'ustl_buy_amt_smtl',
    'tot_frcr_cblc_smtl', 'tot_loan_amt'
]

def main():
    """
    [해외주식] 주문/계좌
    해외주식 체결기준현재잔고[v1_해외주식-008]

    해외주식 체결기준현재잔고 테스트 함수
    
    Parameters:
        - cano (str): 종합계좌번호 (계좌번호 체계(8-2)의 앞 8자리)
        - acnt_prdt_cd (str): 계좌상품코드 (계좌번호 체계(8-2)의 뒤 2자리)
        - wcrc_frcr_dvsn_cd (str): 원화외화구분코드 (01 : 원화  02 : 외화)
        - natn_cd (str): 국가코드 (000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남)
        - tr_mket_cd (str): 거래시장코드 ([Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD)
        - inqr_dvsn_cd (str): 조회구분코드 (00 : 전체  01 : 일반해외주식  02 : 미니스탁)
        - env_dv (str): 실전모의구분 (real:실전, demo:모의)

    Returns:
        - DataFrame: 해외주식 체결기준현재잔고 결과
    
    Example:
        >>> df1, df2, df3 = inquire_present_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, wcrc_frcr_dvsn_cd="02", natn_cd="000", tr_mket_cd="00", inqr_dvsn_cd="00", env_dv="real")  # 실전투자
    """
    try:
        # pandas 출력 옵션 설정
        pd.set_option('display.max_columns', None)  # 모든 컬럼 표시
        pd.set_option('display.width', None)  # 출력 너비 제한 해제
        pd.set_option('display.max_rows', None)  # 모든 행 표시

        # 실전/모의투자 선택 (모의투자 지원 로직)
        env_dv = "real"  # "real": 실전투자, "demo": 모의투자
        logger.info("투자 환경: %s", "실전투자" if env_dv == "real" else "모의투자")

        # 토큰 발급 (모의투자 지원 로직)
        logger.info("토큰 발급 중...")
        if env_dv == "real":
            ka.auth(svr='prod')  # 실전투자용 토큰
        elif env_dv == "demo":
            ka.auth(svr='vps')   # 모의투자용 토큰
        logger.info("토큰 발급 완료")
# -*- coding: utf-8 -*-
"""
Created on 2025-06-30

"""

import sys
import logging

import pandas as pd

sys.path.extend(['../..', '.'])  # kis_auth 파일 경로 추가
import kis_auth as ka
from inquire_paymt_stdr_balance import inquire_paymt_stdr_balance

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 결제기준잔고 [해외주식-064]
##############################################################################################

# 컬럼명 매핑 (한글 변환용)
COLUMN_MAPPING = {
    'pdno': '상품번호',
    'prdt_name': '상품명',
    'cblc_qty13': '잔고수량13',
    'ord_psbl_qty1': '주문가능수량1',
    'avg_unpr3': '평균단가3',
    'ovrs_now_pric1': '해외현재가격1',
    'frcr_pchs_amt': '외화매입금액',
    'frcr_evlu_amt2': '외화평가금액2',
    'evlu_pfls_amt2': '평가손익금액2',
    'bass_exrt': '기준환율',
    'oprt_dtl_dtime': '조작상세일시',
    'buy_crcy_cd': '매수통화코드',
    'thdt_sll_ccld_qty1': '당일매도체결수량1',
    'thdt_buy_ccld_qty1': '당일매수체결수량1',
    'evlu_pfls_rt1': '평가손익율1',
    'tr_mket_name': '거래시장명',
    'natn_kor_name': '국가한글명',
    'std_pdno': '표준상품번호',
    'mgge_qty': '담보수량',
    'loan_rmnd': '대출잔액',
    'prdt_type_cd': '상품유형코드',
    'ovrs_excg_cd': '해외거래소코드',
    'scts_dvsn_name': '유가증권구분명',
    'ldng_cblc_qty': '대여잔고수량',
    'crcy_cd': '통화코드',
    'crcy_cd_name': '통화코드명',
    'frcr_dncl_amt_2': '외화예수금액2',
    'frst_bltn_exrt': '최초고시환율',
    'frcr_evlu_amt2': '외화평가금액2',
    'pchs_amt_smtl_amt': '매입금액합계금액',
    'tot_evlu_pfls_amt': '총평가손익금액',
    'evlu_erng_rt1': '평가수익율1',
    'tot_dncl_amt': '총예수금액',
    'wcrc_evlu_amt_smtl': '원화평가금액합계',
    'tot_asst_amt2': '총자산금액2',
    'frcr_cblc_wcrc_evlu_amt_smtl': '외화잔고원화평가금액합계',
    'tot_loan_amt': '총대출금액',
    'tot_ldng_evlu_amt': '총대여평가금액'
}

# 숫자형 컬럼 정의 (소수점 처리용)
NUMERIC_COLUMNS = [
    '잔고수량13', '주문가능수량1', '평균단가3', '해외현재가격1', '외화매입금액',
    '외화평가금액2', '평가손익금액2', '기준환율', '당일매도체결수량1', '당일매수체결수량1',
    '평가손익율1', '담보수량', '대출잔액', '대여잔고수량', '외화예수금액2',
    '최초고시환율', '매입금액합계금액', '총평가손익금액', '평가수익율1', '총예수금액',
    '원화평가금액합계', '총자산금액2', '외화잔고원화평가금액합계', '총대출금액', '총대여평가금액'
]

def main():
    """
    [해외주식] 주문/계좌
    해외주식 결제기준잔고[해외주식-064]

    해외주식 결제기준잔고 테스트 함수
    
    Parameters:
        - cano (str): 종합계좌번호 ()
        - acnt_prdt_cd (str): 계좌상품코드 ()
        - bass_dt (str): 기준일자 ()
        - wcrc_frcr_dvsn_cd (str): 원화외화구분코드 (01(원화기준),02(외화기준))
        - inqr_dvsn_cd (str): 조회구분코드 (00(전체), 01(일반), 02(미니스탁))

    Returns:
        - DataFrame: 해외주식 결제기준잔고 결과
    
    Example:
        >>> df1, df2, df3 = inquire_paymt_stdr_balance(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod, bass_dt="20250630", wcrc_frcr_dvsn_cd="01", inqr_dvsn_cd="00")
    """
    try:
        # pandas 출력 옵션 설정
        pd.set_option('display.max_columns', None)  # 모든 컬럼 표시
        pd.set_option('display.width', None)  # 출력 너비 제한 해제
        pd.set_option('display.max_rows', None)  # 모든 행 표시

        # 토큰 발급
        logger.info("토큰 발급 중...")
        ka.auth()
        logger.info("토큰 발급 완료")

        trenv = ka.getTREnv()

        # API 호출
        logger.info("API 호출")
        result1, result2, result3 = inquire_paymt_stdr_balance(
            cano=trenv.my_acct,  # 종합계좌번호
            acnt_prdt_cd=trenv.my_prod,  # 계좌상품코드
            bass_dt="20250630",  # 기준일자
            wcrc_frcr_dvsn_cd="01",  # 원화외화구분코드
            inqr_dvsn_cd="00",  # 조회구분코드
        )
        
        # 결과 확인
        results = [result1, result2, result3]
        if all(result is None or result.empty for result in results):
            logger.warning("조회된 데이터가 없습니다.")
            return
        

        # output1 결과 처리
        logger.info("=== output1 조회 ===")
        if not result1.empty:
            logger.info("사용 가능한 컬럼: %s", result1.columns.tolist())
            
            # 통합 컬럼명 한글 변환 (필요한 컬럼만 자동 매핑됨)
            result1 = result1.rename(columns=COLUMN_MAPPING)
            
            # 숫자형 컬럼 처리
            for col in NUMERIC_COLUMNS:
                if col in result1.columns:
                    result1[col] = pd.to_numeric(result1[col], errors='coerce').round(2)
            
            logger.info("output1 결과:")
            print(result1)
        else:
            logger.info("output1 데이터가 없습니다.")

        # output2 결과 처리
        logger.info("=== output2 조회 ===")
        if not result2.empty:
            logger.info("사용 가능한 컬럼: %s", result2.columns.tolist())
            
            # 통합 컬럼명 한글 변환 (필요한 컬럼만 자동 매핑됨)
            result2 = result2.rename(columns=COLUMN_MAPPING)
            

codex
The official LLM checker confirms `inquire-balance` itself does not expose `bass_exrt`/`frst_bltn_exrt` in its listed columns. `inquire-present-balance` does, and I’m checking which output block each field belongs to.
exec
/bin/zsh -lc "sed -n '140,280p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py && sed -n '1,170p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
        logger.info("토큰 발급 완료")
        trenv = ka.getTREnv()


        # API 호출
        logger.info("API 호출")
        result1, result2, result3 = inquire_present_balance(
            cano=trenv.my_acct,  # 종합계좌번호
            acnt_prdt_cd=trenv.my_prod,  # 계좌상품코드
            wcrc_frcr_dvsn_cd="02",  # 원화외화구분코드
            natn_cd="000",  # 국가코드
            tr_mket_cd="00",  # 거래시장코드
            inqr_dvsn_cd="00",  # 조회구분코드
            env_dv=env_dv,  # 실전모의구분
        )
        
        # 결과 확인
        results = [result1, result2, result3]
        if all(result is None or result.empty for result in results):
            logger.warning("조회된 데이터가 없습니다.")
            return
        

        # output1 결과 처리
        logger.info("=== output1 조회 ===")
        if not result1.empty:
            logger.info("사용 가능한 컬럼: %s", result1.columns.tolist())
            
            # 통합 컬럼명 한글 변환 (필요한 컬럼만 자동 매핑됨)
            result1 = result1.rename(columns=COLUMN_MAPPING)
            
            # 숫자형 컬럼 처리
            for col in NUMERIC_COLUMNS:
                if col in result1.columns:
                    result1[col] = pd.to_numeric(result1[col], errors='coerce').round(2)
            
            logger.info("output1 결과:")
            print(result1)
        else:
            logger.info("output1 데이터가 없습니다.")

        # output2 결과 처리
        logger.info("=== output2 조회 ===")
        if not result2.empty:
            logger.info("사용 가능한 컬럼: %s", result2.columns.tolist())
            
            # 통합 컬럼명 한글 변환 (필요한 컬럼만 자동 매핑됨)
            result2 = result2.rename(columns=COLUMN_MAPPING)
            
            # 숫자형 컬럼 처리
            for col in NUMERIC_COLUMNS:
                if col in result2.columns:
                    result2[col] = pd.to_numeric(result2[col], errors='coerce').round(2)
            
            logger.info("output2 결과:")
            print(result2)
        else:
            logger.info("output2 데이터가 없습니다.")

        # output3 결과 처리
        logger.info("=== output3 조회 ===")
        if not result3.empty:
            logger.info("사용 가능한 컬럼: %s", result3.columns.tolist())
            
            # 통합 컬럼명 한글 변환 (필요한 컬럼만 자동 매핑됨)
            result3 = result3.rename(columns=COLUMN_MAPPING)
            
            # 숫자형 컬럼 처리
            for col in NUMERIC_COLUMNS:
                if col in result3.columns:
                    result3[col] = pd.to_numeric(result3[col], errors='coerce').round(2)
            
            logger.info("output3 결과:")
            print(result3)
        else:
            logger.info("output3 데이터가 없습니다.")

        
    except Exception as e:
        logger.error("에러 발생: %s", str(e))
        raise

if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
Created on 2025-06-30

"""

import logging
import time
from typing import Optional, Tuple
import sys

import pandas as pd

sys.path.extend(['../..', '.'])
import kis_auth as ka

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################################################################
# [해외주식] 주문/계좌 > 해외주식 체결기준현재잔고 [v1_해외주식-008]
##############################################################################################

# 상수 정의
API_URL = "/uapi/overseas-stock/v1/trading/inquire-present-balance"

def inquire_present_balance(
    cano: str,  # 종합계좌번호
    acnt_prdt_cd: str,  # 계좌상품코드
    wcrc_frcr_dvsn_cd: str,  # 원화외화구분코드
    natn_cd: str,  # 국가코드
    tr_mket_cd: str,  # 거래시장코드
    inqr_dvsn_cd: str,  # 조회구분코드
    env_dv: str = "real",  # 실전모의구분
    dataframe1: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output1)
    dataframe2: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output2)
    dataframe3: Optional[pd.DataFrame] = None,  # 누적 데이터프레임 (output3)
    tr_cont: str = "",
    depth: int = 0,
    max_depth: int = 10
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    [해외주식] 주문/계좌 
    해외주식 체결기준현재잔고[v1_해외주식-008]
    해외주식 체결기준현재잔고 API를 호출하여 DataFrame으로 반환합니다.
    
    Args:
        cano (str): 계좌번호 체계(8-2)의 앞 8자리
        acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
        wcrc_frcr_dvsn_cd (str): 01 : 원화  02 : 외화
        natn_cd (str): 000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남
        tr_mket_cd (str): [Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD
        inqr_dvsn_cd (str): 00 : 전체  01 : 일반해외주식  02 : 미니스탁
        env_dv (str): 실전모의구분 (real:실전, demo:모의)
        dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
        dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
        dataframe3 (Optional[pd.DataFrame]): 누적 데이터프레임 (output3)
        tr_cont (str): 연속 거래 여부
        depth (int): 현재 재귀 깊이
        max_depth (int): 최대 재귀 깊이 (기본값: 10)
        
    Returns:
        Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: 해외주식 체결기준현재잔고 데이터
        
    Example:
        >>> df1, df2, df3 = inquire_present_balance(
        ...     cano=trenv.my_acct,
        ...     acnt_prdt_cd=trenv.my_prod,
        ...     wcrc_frcr_dvsn_cd="01",
        ...     natn_cd="000",
        ...     tr_mket_cd="00",
        ...     inqr_dvsn_cd="00"
        ... )
        >>> print(df1)
        >>> print(df2)
        >>> print(df3)
    """
    # [필수 파라미터 검증]
    if not cano:
        logger.error("cano is required. (e.g. '810XXXXX')")
        raise ValueError("cano is required. (e.g. '810XXXXX')")
    if not acnt_prdt_cd:
        logger.error("acnt_prdt_cd is required. (e.g. '01')")
        raise ValueError("acnt_prdt_cd is required. (e.g. '01')")
    if not wcrc_frcr_dvsn_cd:
        logger.error("wcrc_frcr_dvsn_cd is required. (e.g. '01')")
        raise ValueError("wcrc_frcr_dvsn_cd is required. (e.g. '01')")
    if not natn_cd:
        logger.error("natn_cd is required. (e.g. '000')")
        raise ValueError("natn_cd is required. (e.g. '000')")
    if not tr_mket_cd:
        logger.error("tr_mket_cd is required. (e.g. '00')")
        raise ValueError("tr_mket_cd is required. (e.g. '00')")
    if not inqr_dvsn_cd:
        logger.error("inqr_dvsn_cd is required. (e.g. '00')")
        raise ValueError("inqr_dvsn_cd is required. (e.g. '00')")

    # 최대 재귀 깊이 체크
    if depth >= max_depth:
        logger.warning("Maximum recursion depth (%d) reached. Stopping further requests.", max_depth)
        return dataframe1 if dataframe1 is not None else pd.DataFrame(), dataframe2 if dataframe2 is not None else pd.DataFrame(), dataframe3 if dataframe3 is not None else pd.DataFrame()
    
    # TR ID 설정 (모의투자 지원 로직)
    if env_dv == "real":
        tr_id = "CTRP6504R"  # 실전투자용 TR ID
    elif env_dv == "demo":
        tr_id = "VTRP6504R"  # 모의투자용 TR ID
    else:
        raise ValueError("env_dv can only be 'real' or 'demo'")

    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "WCRC_FRCR_DVSN_CD": wcrc_frcr_dvsn_cd,
        "NATN_CD": natn_cd,
        "TR_MKET_CD": tr_mket_cd,
        "INQR_DVSN_CD": inqr_dvsn_cd,
    }

    res = ka._url_fetch(api_url=API_URL, ptr_id=tr_id, tr_cont=tr_cont, params=params)

    if res.isOK():
        # output1 처리
        if hasattr(res.getBody(), 'output1'):
            output_data = res.getBody().output1
            if output_data:
                if isinstance(output_data, list):
                    current_data1 = pd.DataFrame(output_data)
                else:
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
                if isinstance(output_data, list):
                    current_data2 = pd.DataFrame(output_data)
                else:
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
        
        # output3 처리
        if hasattr(res.getBody(), 'output3'):
            output_data = res.getBody().output3
            if output_data:
                if isinstance(output_data, list):
                    current_data3 = pd.DataFrame(output_data)
                else:

exec
/bin/zsh -lc "sed -n '170,260p' /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py" in /Users/manager/side/makemoney
 succeeded in 0ms:
                else:
                    current_data3 = pd.DataFrame([output_data])
                
                if dataframe3 is not None:
                    dataframe3 = pd.concat([dataframe3, current_data3], ignore_index=True)
                else:
                    dataframe3 = current_data3
            else:
                if dataframe3 is None:
                    dataframe3 = pd.DataFrame()
        else:
            if dataframe3 is None:
                dataframe3 = pd.DataFrame()
        
        tr_cont = res.getHeader().tr_cont
        
        if tr_cont in ["M", "F"]:
            logger.info("Calling next page...")
            ka.smart_sleep()
            return inquire_present_balance(
                cano=cano,
                acnt_prdt_cd=acnt_prdt_cd,
                wcrc_frcr_dvsn_cd=wcrc_frcr_dvsn_cd,
                natn_cd=natn_cd,
                tr_mket_cd=tr_mket_cd,
                inqr_dvsn_cd=inqr_dvsn_cd,
                env_dv=env_dv,
                dataframe1=dataframe1,
                dataframe2=dataframe2,
                dataframe3=dataframe3,
                tr_cont="N",
                depth=depth + 1,
                max_depth=max_depth
            )
        else:
            logger.info("Data fetch complete.")
            return dataframe1, dataframe2, dataframe3
    else:
        logger.error("API call failed: %s - %s", res.getErrorCode(), res.getErrorMessage())
        res.printError(API_URL)
        # 이미 수집된 데이터가 있으면 그것을 반환, 없으면 빈 DataFrame 반환
        if dataframe1 is not None and not dataframe1.empty:
            logger.info("Returning already collected data due to API error.")
            return dataframe1, dataframe2 if dataframe2 is not None else pd.DataFrame(), dataframe3 if dataframe3 is not None else pd.DataFrame()
        else:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

exec
/bin/zsh -lc "sed -n '10680,10895p' '/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv'" in /Users/manager/side/makemoney
 succeeded in 0ms:
    ...     FK200="""",
    ...     NK200=""""
    ... )
     print(df1)
     print(df2)","{
    'cano': '종합계좌번호',
    'acnt_prdt_cd': '계좌상품코드',
    'prdt_type_cd': '상품유형코드',
    'ovrs_pdno': '해외상품번호',
    'frcr_evlu_pfls_amt': '외화평가손익금액',
    'evlu_pfls_rt': '평가손익율',
    'pchs_avg_pric': '매입평균가격',
    'ovrs_cblc_qty': '해외잔고수량',
    'ord_psbl_qty': '주문가능수량',
    'frcr_pchs_amt1': '외화매입금액1',
    'ovrs_stck_evlu_amt': '해외주식평가금액',
    'now_pric2': '현재가격2',
    'tr_crcy_cd': '거래통화코드',
    'ovrs_excg_cd': '해외거래소코드',
    'loan_type_cd': '대출유형코드',
    'loan_dt': '대출일자',
    'expd_dt': '만기일자',
    'frcr_pchs_amt1': '외화매입금액1',
    'ovrs_rlzt_pfls_amt': '해외실현손익금액',
    'ovrs_tot_pfls': '해외총손익',
    'rlzt_erng_rt': '실현수익율',
    'tot_evlu_pfls_amt': '총평가손익금액',
    'tot_pftrt': '총수익률',
    'frcr_buy_amt_smtl1': '외화매수금액합계1',
    'ovrs_rlzt_pfls_amt2': '해외실현손익금액2',
    'frcr_buy_amt_smtl2': '외화매수금액합계2'
}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance/inquire_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_balance/chk_inquire_balance.py
overseas_stock,주문/계좌,해외주식 체결기준현재잔고,inquire_present_balance,[해외주식] 주문/계좌 해외주식 체결기준현재잔고[v1_해외주식-008] 해외주식 체결기준현재잔고 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 계좌번호 체계(8-2)의 앞 8자리
acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
wcrc_frcr_dvsn_cd (str): 01 : 원화  02 : 외화
natn_cd (str): 000 전체 840 미국 344 홍콩 156 중국 392 일본 704 베트남
tr_mket_cd (str): [Request body NATN_CD 000 설정] 00 : 전체  [Request body NATN_CD 840 설정] 00 : 전체 01 : 나스닥(NASD) 02 : 뉴욕거래소(NYSE) 03 : 미국(PINK SHEETS) 04 : 미국(OTCBB) 05 : 아멕스(AMEX)  [Request body NATN_CD 156 설정] 00 : 전체 01 : 상해B 02 : 심천B 03 : 상해A 04 : 심천A  [Request body NATN_CD 392 설정] 01 : 일본  [Request body NATN_CD 704 설정] 01 : 하노이거래 02 : 호치민거래소  [Request body NATN_CD 344 설정] 01 : 홍콩 02 : 홍콩CNY 03 : 홍콩USD
inqr_dvsn_cd (str): 00 : 전체  01 : 일반해외주식  02 : 미니스탁
env_dv (str): 실전모의구분 (real:실전, demo:모의)
dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
dataframe3 (Optional[pd.DataFrame]): 누적 데이터프레임 (output3)
tr_cont (str): 연속 거래 여부
depth (int): 현재 재귀 깊이
max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: 해외주식 체결기준현재잔고 데이터","     df1, df2, df3 = inquire_present_balance(
    ...     cano=trenv.my_acct,
    ...     acnt_prdt_cd=trenv.my_prod,
    ...     wcrc_frcr_dvsn_cd=""01"",
    ...     natn_cd=""000"",
    ...     tr_mket_cd=""00"",
    ...     inqr_dvsn_cd=""00""
    ... )
     print(df1)
     print(df2)
     print(df3)","{
    'cblc_qty13': '잔고수량13',
    'thdt_buy_ccld_qty1': '당일매수체결수량1',
    'thdt_sll_ccld_qty1': '당일매도체결수량1',
    'ccld_qty_smtl1': '체결수량합계1',
    'ord_psbl_qty1': '주문가능수량1',
    'frcr_pchs_amt': '외화매입금액',
    'frcr_evlu_amt2': '외화평가금액2',
    'evlu_pfls_amt2': '평가손익금액2',
    'evlu_pfls_rt1': '평가손익율1',
    'pdno': '상품번호',
    'bass_exrt': '기준환율',
    'buy_crcy_cd': '매수통화코드',
    'ovrs_now_pric1': '해외현재가격1',
    'avg_unpr3': '평균단가3',
    'tr_mket_name': '거래시장명',
    'natn_kor_name': '국가한글명',
    'pchs_rmnd_wcrc_amt': '매입잔액원화금액',
    'thdt_buy_ccld_frcr_amt': '당일매수체결외화금액',
    'thdt_sll_ccld_frcr_amt': '당일매도체결외화금액',
    'unit_amt': '단위금액',
    'std_pdno': '표준상품번호',
    'prdt_type_cd': '상품유형코드',
    'loan_rmnd': '대출잔액',
    'loan_dt': '대출일자',
    'loan_expd_dt': '대출만기일자',
    'ovrs_excg_cd': '해외거래소코드',
    'item_lnkg_excg_cd': '종목연동거래소코드',
    'crcy_cd': '통화코드',
    'frcr_buy_amt_smtl': '외화매수금액합계',
    'frcr_sll_amt_smtl': '외화매도금액합계',
    'frcr_dncl_amt_2': '외화예수금액2',
    'frst_bltn_exrt': '최초고시환율',
    'frcr_buy_mgn_amt': '외화매수증거금액',
    'frcr_etc_mgna': '외화기타증거금',
    'frcr_drwg_psbl_amt_1': '외화출금가능금액1',
    'frcr_evlu_amt2': '출금가능원화금액',
    'acpl_cstd_crcy_yn': '현지보관통화여부',
    'nxdy_frcr_drwg_psbl_amt': '익일외화출금가능금액',
    'output3': '응답상세3',
    'pchs_amt_smtl': '매입금액합계',
    'evlu_amt_smtl': '평가금액합계',
    'evlu_pfls_amt_smtl': '평가손익금액합계',
    'dncl_amt': '예수금액',
    'cma_evlu_amt': 'CMA평가금액',
    'tot_dncl_amt': '총예수금액',
    'etc_mgna': '기타증거금',
    'wdrw_psbl_tot_amt': '인출가능총금액',
    'frcr_evlu_tota': '외화평가총액',
    'evlu_erng_rt1': '평가수익율1',
    'pchs_amt_smtl_amt': '매입금액합계금액',
    'evlu_amt_smtl_amt': '평가금액합계금액',
    'tot_evlu_pfls_amt': '총평가손익금액',
    'tot_asst_amt': '총자산금액',
    'buy_mgn_amt': '매수증거금액',
    'mgna_tota': '증거금총액',
    'frcr_use_psbl_amt': '외화사용가능금액',
    'ustl_sll_amt_smtl': '미결제매도금액합계',
    'ustl_buy_amt_smtl': '미결제매수금액합계',
    'tot_frcr_cblc_smtl': '총외화잔고합계',
    'tot_loan_amt': '총대출금액'
}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance/inquire_present_balance.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py
overseas_stock,주문/계좌,해외주식 지정가체결내역조회,inquire_algo_ccnl,"해외주식 TWAP, VWAP 주문에 대한 체결내역 조회 API로 지정가 주문번호조회 API를 수행 후 조회해야합니다","cano (str): [필수] 계좌번호
acnt_prdt_cd (str): [필수] 계좌상품코드 (ex. 01)
ord_dt (str): 주문일자
ord_gno_brno (str): 주문채번지점번호
odno (str): 주문번호 (ex. 지정가주문번호 TTTC6058R에서 조회된 주문번호 입력)
ttlz_icld_yn (str): 집계포함여부
NK200 (str): 연속조회키200
FK200 (str): 연속조회조건200
tr_cont (str): 연속거래여부
dataframe (Optional[pd.DataFrame]): 누적 데이터프레임
dataframe3 (Optional[pd.DataFrame]): 누적 데이터프레임3
depth (int): 내부 재귀깊이 (자동관리)
max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: (output, output3) 체결내역 데이터","     result, result3 = inquire_algo_ccnl(cano=trenv.my_acct, acnt_prdt_cd=trenv.my_prod)
     print(result)
     print(result3)","{
    'CCLD_SEQ': '체결순번',
    'CCLD_BTWN': '체결시간',
    'PDNO': '상품번호',
    'ITEM_NAME': '종목명',
    'FT_CCLD_QTY': 'FT체결수량',
    'FT_CCLD_UNPR3': 'FT체결단가',
    'FT_CCLD_AMT3': 'FT체결금액',
    'ODNO': '주문번호',
    'TRAD_DVSN_NAME': '매매구분명',
    'FT_ORD_QTY': 'FT주문수량',
    'FT_ORD_UNPR3': 'FT주문단가',
    'ORD_TMD': '주문시각',
    'SPLT_BUY_ATTR_NAME': '분할매수속성명',
    'TR_CRCY': '거래통화',
    'CCLD_CNT': '체결건수'
}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_algo_ccnl/inquire_algo_ccnl.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_algo_ccnl/chk_inquire_algo_ccnl.py
overseas_stock,주문/계좌,해외주식 기간손익,inquire_period_profit,[해외주식] 주문/계좌 해외주식 기간손익[v1_해외주식-032] 해외주식 기간손익 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 계좌번호 체계(8-2)의 앞 8자리
acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
ovrs_excg_cd (str): 공란 : 전체,  NASD : 미국, SEHK : 홍콩, SHAA : 중국, TKSE : 일본, HASE : 베트남
natn_cd (str): 공란(Default)
crcy_cd (str): 공란 : 전체 USD : 미국달러, HKD : 홍콩달러, CNY : 중국위안화,  JPY : 일본엔화, VND : 베트남동
pdno (str): 공란 : 전체
inqr_strt_dt (str): YYYYMMDD
inqr_end_dt (str): YYYYMMDD
wcrc_frcr_dvsn_cd (str): 01 : 외화, 02 : 원화
FK200 (str): 연속조회검색조건200
NK200 (str): 연속조회키200
dataframe1 (Optional[pd.DataFrame]): 누적 데이터프레임 (output1)
dataframe2 (Optional[pd.DataFrame]): 누적 데이터프레임 (output2)
tr_cont (str): 연속 거래 여부
depth (int): 현재 재귀 깊이
max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 해외주식 기간손익 데이터","     df1, df2 = inquire_period_profit(
    ...     cano=trenv.my_acct,
    ...     acnt_prdt_cd=trenv.my_prod,
    ...     ovrs_excg_cd=""NASD"",
    ...     natn_cd="""",
    ...     crcy_cd=""USD"",
    ...     pdno="""",
    ...     inqr_strt_dt=""20230101"",
    ...     inqr_end_dt=""20231231"",
    ...     wcrc_frcr_dvsn_cd=""01"",
    ...     FK200="""",
    ...     NK200=""""
    ... )
     print(df1)
     print(df2)","{
    'trad_day': '매매일',
    'ovrs_pdno': '해외상품번호',
    'slcl_qty': '매도청산수량',
    'pchs_avg_pric': '매입평균가격',
    'frcr_pchs_amt1': '외화매입금액1',
    'avg_sll_unpr': '평균매도단가',
    'frcr_sll_amt_smtl1': '외화매도금액합계1',
    'stck_sll_tlex': '주식매도제비용',
    'ovrs_rlzt_pfls_amt': '해외실현손익금액',
    'pftrt': '수익률',
    'exrt': '환율',
    'ovrs_excg_cd': '해외거래소코드',
    'frst_bltn_exrt': '최초고시환율',
    'stck_sll_amt_smtl': '주식매도금액합계',
    'stck_buy_amt_smtl': '주식매수금액합계',
    'smtl_fee1': '합계수수료1',
    'excc_dfrm_amt': '정산지급금액',
    'ovrs_rlzt_pfls_tot_amt': '해외실현손익총금액',
    'tot_pftrt': '총수익률',
    'bass_dt': '기준일자',
    'exrt': '환율'
}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_period_profit/inquire_period_profit.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py
overseas_stock,주문/계좌,해외주식 매수가능금액조회,inquire_psamount,[해외주식] 주문/계좌 해외주식 매수가능금액조회[v1_해외주식-014] 해외주식 매수가능금액조회 API를 호출하여 DataFrame으로 반환합니다.,"cano (str): 계좌번호 체계(8-2)의 앞 8자리
acnt_prdt_cd (str): 계좌번호 체계(8-2)의 뒤 2자리
ovrs_excg_cd (str): NASD : 나스닥 / NYSE : 뉴욕 / AMEX : 아멕스 SEHK : 홍콩 / SHAA : 중국상해 / SZAA : 중국심천 TKSE : 일본 / HASE : 하노이거래소 / VNSE : 호치민거래소
ovrs_ord_unpr (str): 해외주문단가 (23.8) 정수부분 23자리, 소수부분 8자리
item_cd (str): 종목코드
env_dv (str): 실전모의구분 (real:실전, demo:모의)
tr_cont (str): 연속 거래 여부
dataframe (Optional[pd.DataFrame]): 누적 데이터프레임
depth (int): 현재 재귀 깊이
max_depth (int): 최대 재귀 깊이 (기본값: 10)",Optional[pd.DataFrame]: 해외주식 매수가능금액조회 데이터,"     df = inquire_psamount(
    ...     cano=trenv.my_acct,
    ...     acnt_prdt_cd=trenv.my_prod,
    ...     ovrs_excg_cd=""NASD"",
    ...     ovrs_ord_unpr=""1.4"",
    ...     item_cd=""QQQ""
    ... )
     print(df)","{

web search: 
web search: "해외주식 체결기준현재잔고" "frst_bltn_exrt" "output3"
web search: 
web search: site:github.com/koreainvestment/open-trading-api overseas_stock exchange rate frst_bltn_exrt
exec
/bin/zsh -lc "rg -n \"환율|exchange|exrt|종목/지수/환율|inquire.*chart|daily.*chart|period.*price\" /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock /var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS\\ Code\\ Assistant\\ MCP/data.csv" in /Users/manager/side/makemoney
 succeeded in 0ms:
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py:36:    'exrt': '환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py:38:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py:46:    'exrt': '환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_profit/chk_inquire_period_profit.py:52:    'stck_sll_tlex', 'ovrs_rlzt_pfls_amt', 'pftrt', 'exrt', 'frst_bltn_exrt',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/chk_inquire_time_itemchartprice.py:14:from inquire_time_itemchartprice import inquire_time_itemchartprice
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/chk_inquire_time_itemchartprice.py:71:        >>> df1, df2 = inquire_time_itemchartprice(auth="", excd="NAS", symb="TSLA", nmin="5", pinc="1", next="", nrec="120", fill="", keyb="")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/chk_inquire_time_itemchartprice.py:88:        result1, result2 = inquire_time_itemchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py:26:API_URL = "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py:28:def inquire_time_itemchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py:69:        >>> df1, df2 = inquire_time_itemchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py:159:            return inquire_time_itemchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:358:domestic_bond,기본시세,장내채권 기간별시세(일),inquire_daily_itemchartprice,[장내채권] 기본시세 장내채권 기간별시세(일)[국내주식-159] 장내채권 기간별시세(일) API를 호출하여 DataFrame으로 반환합니다.,"fid_cond_mrkt_div_code (str): 조건 시장 구분 코드 (필수)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:363:max_depth (int): 최대 재귀 깊이 (기본값: 10)",Optional[pd.DataFrame]: 장내채권 기간별시세(일) 데이터,"     df = inquire_daily_itemchartprice(""B"", ""KR2033022D33"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:371:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_bond/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_bond/inquire_daily_itemchartprice/chk_inquire_daily_itemchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:468:    'expd_rdpt_rt': '만기상환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:500:    'expd_exts_srdp_rt': '만기연장분할상환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:546:    'bond_expd_rdpt_rt': '채권만기상환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:572:    'expd_exts_srdp_rt': '만기연장분할상환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:573:    'expd_rdpt_rt': '만기상환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1380:domestic_futureoption,기본시세,선물옵션기간별시세(일/주/월/년),inquire_daily_fuopchartprice,"(지수)선물옵션 기간별시세 데이터(일/주/월/년) 조회 (최대 100건 조회) 실전계좌의 경우, 한 번의 호출에 최대 100건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다. 모의계좌의 경우, 한 번의 호출에 최대 100건까지 확인 가능하며, 이후의 값은 연속조회를 통해 확인하실 수 있습니다.","fid_cond_mrkt_div_code (str): [필수] FID 조건 시장 분류 코드 (ex. F: 지수선물, O: 지수옵션)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1385:env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)","Tuple[pd.DataFrame, pd.DataFrame]: (기본정보, 차트데이터) 튜플","     output1, output2 = inquire_daily_fuopchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1433:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_daily_fuopchartprice/inquire_daily_fuopchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_daily_fuopchartprice/chk_inquire_daily_fuopchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1459:domestic_futureoption,기본시세,선물옵션 분봉조회,inquire_time_fuopchartprice,"선물옵션 분봉조회 API입니다. 실전계좌의 경우, 한 번의 호출에 최대 102건까지 확인 가능하며, FID_INPUT_DATE_1(입력날짜), FID_INPUT_HOUR_1(입력시간)을 이용하여 다음 조회 가능합니다.","fid_cond_mrkt_div_code (str): [필수] FID 조건 시장 분류 코드 (ex. F: 지수선물, O: 지수옵션)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1465:fid_input_hour_1 (str): [필수] FID 입력 시간1 (ex. 100000)","Tuple[pd.DataFrame, pd.DataFrame]: 선물옵션 분봉 데이터 (output1, output2)","     df1, df2 = inquire_time_fuopchartprice(""F"", ""101T12"", ""60"", ""Y"", ""N"", ""20230901"", ""100000"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:1507:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_time_fuopchartprice/inquire_time_fuopchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_futureoption/inquire_time_fuopchartprice/chk_inquire_time_fuopchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2719:    'usd_frst_bltn_exrt': '미국달러최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2720:    'hkd_frst_bltn_exrt': '홍콩달러최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2721:    'jpy_frst_bltn_exrt': '일본엔화최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:2722:    'cny_frst_bltn_exrt': '중국위안화최초고시환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3722:domestic_stock,기본시세,주식일별분봉조회,inquire_time_dailychartprice,"주식일별분봉조회 API입니다. 실전계좌의 경우, 한 번의 호출에 최대 120건까지 확인 가능하며, FID_INPUT_DATE_1, FID_INPUT_HOUR_1 이용하여 과거일자 분봉조회 가능합니다. ※ 과거 분봉 조회 시, 당사 서버에서 보관하고 있는 만큼의 데이터만 확인이 가능합니다. (최대 1년 분봉 보관)","fid_cond_mrkt_div_code (str): [필수] 시장 분류 코드 (ex. J:주식,NX:NXT,UN:통합)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3727:fid_fake_tick_incu_yn (str): 허봉 포함 여부 (기본값: """")","Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터, output2 데이터)","     output1, output2 = inquire_time_dailychartprice(""J"", ""005930"", ""130000"", ""20241023"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3746:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_time_dailychartprice/inquire_time_dailychartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_time_dailychartprice/chk_inquire_time_dailychartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3747:domestic_stock,기본시세,국내주식기간별시세(일/주/월/년),inquire_daily_itemchartprice,"국내주식기간별시세(일/주/월/년) API입니다. 실전계좌/모의계좌의 경우, 한 번의 호출에 최대 100건까지 확인 가능합니다.","env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3753:fid_org_adj_prc (str): [필수] 수정주가 원주가 가격 여부 (ex. 0:수정주가 1:원주가)","Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터, output2 데이터)","     df1, df2 = inquire_daily_itemchartprice(""real"", ""J"", ""005930"", ""20220101"", ""20220809"", ""D"", ""1"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:3799:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/chk_inquire_daily_itemchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4017:domestic_stock,기본시세,주식당일분봉조회,inquire_time_itemchartprice,"주식당일분봉조회 API입니다. 실전계좌/모의계좌의 경우, 한 번의 호출에 최대 30건까지 확인 가능합니다. ※ 당일 분봉 데이터만 제공됩니다. (전일자 분봉 미제공) ※ input > FID_INPUT_HOUR_1 에 미래일시 입력 시에 현재가로 조회됩니다. ex) 오전 10시에 113000 입력 시에 오전 10시~11시30분 사이의 데이터가 오전 10시 값으로 조회됨 ※ output2의 첫번째 배열의 체결량(cntg_vol)은 첫체결이 발생되기 전까지는 이전 분봉의 체결량이 해당 위치에 표시됩니다. 해당 분봉의 첫 체결이 발생되면 해당 이전분 체결량이 두번째 배열로 이동되면서 새로운 체결량으로 업데이트됩니다.","env_dv (str): [필수] 실전모의구분 (ex. real:실전, demo:모의)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4022:fid_etc_cls_code (str): [필수] 기타 구분 코드","Tuple[pd.DataFrame, pd.DataFrame]: (output1 데이터, output2 데이터)","     output1, output2 = inquire_time_itemchartprice(env_dv=""real"", fid_cond_mrkt_div_code=""J"", fid_input_iscd=""005930"", fid_input_hour_1=""093000"", fid_pw_data_incu_yn=""Y"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4041:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_time_itemchartprice/chk_inquire_time_itemchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4107:domestic_stock,업종/기타,국내주식업종기간별시세(일/주/월/년),inquire_daily_indexchartprice,[국내주식] 업종/기타 국내주식업종기간별시세(일_주_월_년)[v1_국내주식-021] 국내주식업종기간별시세(일_주_월_년) API를 호출하여 DataFrame으로 반환합니다.,"fid_cond_mrkt_div_code (str): 업종 : U
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4117:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 국내주식업종기간별시세(일_주_월_년) 데이터","     df1, df2 = inquire_daily_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4125:     df1, df2 = inquire_daily_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4159:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_daily_indexchartprice/inquire_daily_indexchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_daily_indexchartprice/chk_inquire_daily_indexchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4226:domestic_stock,업종/기타,업종 분봉조회,inquire_time_indexchartprice,[국내주식] 업종/기타 업종 분봉조회[v1_국내주식-045] 업종 분봉조회 API를 호출하여 DataFrame으로 반환합니다.,"fid_cond_mrkt_div_code (str): FID 조건 시장 분류 코드 (예: 'U')
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4235:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 업종 분봉조회 데이터","     df1, df2 = inquire_time_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:4270:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_time_indexchartprice/chk_inquire_time_indexchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:9910:overseas_futureoption,기본시세,해외선물 분봉조회,inquire_time_futurechartprice,[해외선물옵션] 기본시세 해외선물 분봉조회[해외선물-016] 해외선물 분봉조회 API를 호출하여 DataFrame으로 반환합니다.,"srs_cd (str): ex) CNHU24 ※ 종목코드 ""포럼 > FAQ > 종목정보 다운로드(해외) - 해외지수선물"" 참고
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:9922:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 해외선물 분봉조회 데이터","     df1, df2 = inquire_time_futurechartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:9948:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_futureoption/inquire_time_futurechartprice/inquire_time_futurechartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_futureoption/inquire_time_futurechartprice/chk_inquire_time_futurechartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10436:overseas_futureoption,기본시세,해외옵션 분봉조회,inquire_time_optchartprice,"해외옵션 분봉조회 API입니다. 한 번의 호출에 120건까지 확인 가능하며, QRY_TP, INDEX_KEY 를 이용하여 다음조회 가능합니다. ※ 다음조회 방법 (처음조회) ""QRY_TP"":""Q"", ""QRY_CNT"":""120"", ""INDEX_KEY"":"""" (다음조회) ""QRY_TP"":""P"", ""QRY_CNT"":""120"", ""INDEX_KEY"":""20240902         5""  ◀ 이전 호출의 ""output1 > index_key"" 기입 (중요) 해외옵션시세 출력값을 해석하실 때 focode.mst(해외지수옵션 종목마스터파일), fostkcode.mst(해외주식옵션 종목마스터파일)에 있는 sCalcDesz(계산 소수점) 값을 활용하셔야 정확한 값을 받아오실 수 있습니다. - focode.mst(해외지수옵션 종목마스터파일), (해외주식옵션 종목마스터파일) 다운로드 방법 1) focode.mst(해외지수옵션 종목마스터파일) : 포럼 > FAQ > 종목정보 다운로드(해외) - 해외지수옵션 클릭하여 다운로드 후 Github의 헤더정보(https://github.com/koreainvestment/open-trading-api/blob/main/stocks_info/해외옵션정보.h)를 참고하여 해석 2) fostkcode.mst(해외주식옵션 종목마스터파일) : 포럼 > FAQ > 종목정보 다운로드(해외) - 해외주식옵션 클릭하여 다운로드 후 Github의 헤더정보(https://github.com/koreainvestment/open-trading-api/blob/main/stocks_info/해외주식옵션정보.h)를 참고하여 해석 - 소수점 계산 시, focode.mst(해외지수옵션 종목마스터파일), fostkcode.mst(해외주식옵션 종목마스터파일)의 sCalcDesz(계산 소수점) 값 참고 EX) focode.mst 파일의 sCalcDesz(계산 소수점) 값 품목코드 OES 계산소수점 -2 → 시세 7525 수신 시 75.25 로 해석 품목코드 O6E 계산소수점 -4 → 시세 54.0 수신 시 0.0054 로 해석","srs_cd (str): [필수] 종목코드 (ex. OESU24 C5500)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10448:max_depth (int): 최대 재귀 횟수 제한","Tuple[pd.DataFrame, pd.DataFrame]: (output1 DataFrame, output2 DataFrame)","     df1, df2 = inquire_time_optchartprice(""OESU24 C5500"", ""CME"", ""20"")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10465:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_futureoption/inquire_time_optchartprice/inquire_time_optchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_futureoption/inquire_time_optchartprice/chk_inquire_time_optchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10745:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10766:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10867:    'exrt': '환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10869:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10877:    'exrt': '환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:10904:    'exrt': '환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11123:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11141:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11201:    'erlm_exrt': '등록환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11352:    'bass_exrt': '기준환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11572:overseas_stock,기본시세,해외지수분봉조회,inquire_time_indexchartprice,[해외주식] 기본시세 해외지수분봉조회[v1_해외주식-031] 해외지수분봉조회 API를 호출하여 DataFrame으로 반환합니다.,"fid_cond_mrkt_div_code (str): N 해외지수 X 환율 KX 원화환율
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11580:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 해외지수분봉조회 데이터","     df1, df2 = inquire_time_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11606:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_time_indexchartprice/chk_inquire_time_indexchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11607:overseas_stock,기본시세,해외주식분봉조회,inquire_time_itemchartprice,[해외주식] 기본시세 해외주식분봉조회[v1_해외주식-030] 해외주식분봉조회 API를 호출하여 DataFrame으로 반환합니다.,"auth (str): """" 공백으로 입력
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11620:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 해외주식분봉조회 데이터","     df1, df2 = inquire_time_itemchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11645:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_time_itemchartprice/chk_inquire_time_itemchartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11684:    't_rate': '당일환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11685:    'p_rate': '전일환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11708:overseas_stock,기본시세,해외주식 종목/지수/환율기간별시세(일/주/월/년),inquire_daily_chartprice,[해외주식] 기본시세 해외주식 종목_지수_환율기간별시세(일_주_월_년)[v1_해외주식-012] 해외주식 종목_지수_환율기간별시세(일_주_월_년) API를 호출하여 DataFrame으로 반환합니다.,"fid_cond_mrkt_div_code (str): N: 해외지수, X 환율, I: 국채, S:금선물
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11718:max_depth (int): 최대 재귀 깊이 (기본값: 10)","Tuple[pd.DataFrame, pd.DataFrame]: 해외주식 종목_지수_환율기간별시세(일_주_월_년) 데이터","     df1, df2 = inquire_daily_chartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:11747:}",https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py,https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:12118:exchange_cd (str): [필수] 거래소코드
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/MCP/KIS Code Assistant MCP/data.csv:12136:    'exchange_cd': '거래소코드',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_trans/chk_inquire_period_trans.py:46:    'erlm_exrt': '등록환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_period_trans/chk_inquire_period_trans.py:59:    'dmst_wcrc_fee', 'ovrs_wcrc_fee', 'erlm_exrt', 'frcr_buy_amt_smtl', 'frcr_sll_amt_smtl',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/news_title/news_title.py:31:    exchange_cd: str = "",      # [필수] 거래소코드
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/news_title/news_title.py:49:        exchange_cd (str): [필수] 거래소코드
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/news_title/news_title.py:80:        "EXCHANGE_CD": exchange_cd,   # 거래소코드
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/news_title/news_title.py:103:                info_gb, class_cd, nation_cd, exchange_cd, symb, data_dt, data_tm, cts, "N", dataframe, depth + 1, max_depth
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/price_detail/chk_price_detail.py:55:    't_rate': '당일환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/price_detail/chk_price_detail.py:56:    'p_rate': '전일환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/price_detail/chk_price_detail.py:69:                    '52주최저가', 'PER', 'PBR', 'EPS', 'BPS', '원환산당일가격', '원환산당일대비', '원환산당일등락', '원환산전일가격', '원환산전일대비', '원환산전일등락', '당일환율', '전일환율', '액면가', '거래량', '거래대금']
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/news_title/chk_news_title.py:32:    'exchange_cd': '거래소코드',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/news_title/chk_news_title.py:56:            exchange_cd="",
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:36:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:57:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:91:    'frcr_pchs_amt', 'frcr_evlu_amt2', 'evlu_pfls_amt2', 'evlu_pfls_rt1', 'bass_exrt',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_present_balance/chk_inquire_present_balance.py:94:    'frst_bltn_exrt', 'frcr_buy_mgn_amt', 'frcr_etc_mgna', 'frcr_drwg_psbl_amt_1', 'frcr_evlu_amt2',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/chk_inquire_time_indexchartprice.py:14:from inquire_time_indexchartprice import inquire_time_indexchartprice
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/chk_inquire_time_indexchartprice.py:55:        - fid_cond_mrkt_div_code (str): 조건 시장 분류 코드 (N 해외지수 X 환율 KX 원화환율)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/chk_inquire_time_indexchartprice.py:64:        >>> df1, df2 = inquire_time_indexchartprice(fid_cond_mrkt_div_code="N", fid_input_iscd="TSLA", fid_hour_cls_code="0", fid_pw_data_incu_yn="Y")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/chk_inquire_time_indexchartprice.py:87:        result1, result2 = inquire_time_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py:26:API_URL = "/uapi/overseas-price/v1/quotations/inquire-time-indexchartprice"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py:28:def inquire_time_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py:45:        fid_cond_mrkt_div_code (str): N 해외지수 X 환율 KX 원화환율
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py:59:        >>> df1, df2 = inquire_time_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_time_indexchartprice/inquire_time_indexchartprice.py:144:            return inquire_time_indexchartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:35:    'bass_exrt': '기준환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:53:    'frst_bltn_exrt': '최초고시환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:69:    '외화평가금액2', '평가손익금액2', '기준환율', '당일매도체결수량1', '당일매수체결수량1',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_paymt_stdr_balance/chk_inquire_paymt_stdr_balance.py:71:    '최초고시환율', '매입금액합계금액', '총평가손익금액', '평가수익율1', '총예수금액',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/foreign_margin/chk_foreign_margin.py:34:    'bass_exrt': '기준환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/foreign_margin/chk_foreign_margin.py:40:    '외화일반주문가능금액', '외화주문가능금액', '통합주문가능금액', '기준환율'
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_psamount/chk_inquire_psamount.py:34:    'exrt': '환율',
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:14:from inquire_daily_chartprice import inquire_daily_chartprice
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:21:# [해외주식] 기본시세 > 해외주식 종목_지수_환율기간별시세(일_주_월_년)[v1_해외주식-012]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:51:    해외주식 종목_지수_환율기간별시세(일_주_월_년)[v1_해외주식-012]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:53:    해외주식 종목_지수_환율기간별시세(일_주_월_년) 테스트 함수
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:56:        - fid_cond_mrkt_div_code (str): FID 조건 시장 분류 코드 (N: 해외지수, X 환율, I: 국채, S:금선물)
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:64:        - DataFrame: 해외주식 종목_지수_환율기간별시세(일_주_월_년) 결과
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:67:        >>> df1, df2 = inquire_daily_chartprice(fid_cond_mrkt_div_code="N", fid_input_iscd=".DJI", fid_input_date_1="20250101", fid_input_date_2="20250131", fid_period_div_code="D", env_dv="real")  # 실전투자
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:68:        >>> df1, df2 = inquire_daily_chartprice(fid_cond_mrkt_div_code="N", fid_input_iscd=".DJI", fid_input_date_1="20250101", fid_input_date_2="20250131", fid_period_div_code="D", env_dv="demo")  # 모의투자
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:92:        logger.info("API 호출 시작: 해외주식 종목_지수_환율기간별시세(일_주_월_년) (%s)", "실전투자" if env_dv == "real" else "모의투자")
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/chk_inquire_daily_chartprice.py:93:        result1, result2 = inquire_daily_chartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:22:# [해외주식] 기본시세 > 해외주식 종목_지수_환율기간별시세(일_주_월_년)[v1_해외주식-012]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:26:API_URL = "/uapi/overseas-price/v1/quotations/inquire-daily-chartprice"
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:28:def inquire_daily_chartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:43:    해외주식 종목_지수_환율기간별시세(일_주_월_년)[v1_해외주식-012]
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:44:    해외주식 종목_지수_환율기간별시세(일_주_월_년) API를 호출하여 DataFrame으로 반환합니다.
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:47:        fid_cond_mrkt_div_code (str): N: 해외지수, X 환율, I: 국채, S:금선물
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:60:        Tuple[pd.DataFrame, pd.DataFrame]: 해외주식 종목_지수_환율기간별시세(일_주_월_년) 데이터
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:63:        >>> df1, df2 = inquire_daily_chartprice(
/var/folders/8r/plkrrtvj4fgd9fll227y0m3w0000gp/T/tmp.CYAtlcLFCG/open-trading-api/examples_llm/overseas_stock/inquire_daily_chartprice/inquire_daily_chartprice.py:160:            return inquire_daily_chartprice(

codex
Use **`VTRP6504R` present-balance**, not `VTTS3012R`.

- `VTTS3012R` `/uapi/overseas-stock/v1/trading/inquire-balance`: I do **not** see FX fields in the official sample schema. No `frst_bltn_exrt`, no `bass_exrt`.
- `VTRP6504R` `/uapi/overseas-stock/v1/trading/inquire-present-balance`: has the FX fields.
  - Per-position: `output1[].bass_exrt` = `기준환율`
  - Per-currency/cash: `output2[].frst_bltn_exrt` = `최초고시환율`
  - `output3` is summary totals, not the FX source.

Recommendation: if you already need KRW-base overseas valuation, call `inquire-present-balance` with `WCRC_FRCR_DVSN_CD=01`, `NATN_CD=000`, `TR_MKET_CD=00`, `INQR_DVSN_CD=00`, then use:

```text
USD/KRW = output1 row where crcy_cd/buy_crcy_cd == "USD" -> bass_exrt
fallback = output2 row where crcy_cd == "USD" -> frst_bltn_exrt
fallback = config default, e.g. DEFAULT_USD_KRW
```

Dedicated FX fallback exists via overseas quotation chart APIs, e.g. `inquire-daily-chartprice` with `FID_COND_MRKT_DIV_CODE=X`, but it is less clean for account valuation than `VTRP6504R`.

Sources: KIS official GitHub samples for `inquire_balance` and `inquire_present_balance`, plus KIS portal listing for overseas quotation FX period APIs.
tokens used
138,991

```

## Concise summary

Provider completed successfully. Review the raw output for details.

## Action items

- Review the response and extract decisions you want to apply.
- Capture follow-up implementation tasks if needed.
