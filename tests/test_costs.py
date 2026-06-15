from trader.execution.costs import BpsCostModel, MarketCostModel, DEFAULT_COSTS
from trader.core.events import Market, Side

def test_bps_cost_is_notional_times_bps():
    m = BpsCostModel(bps=5.0)  # 5bp
    assert m.commission(price=100.0, quantity=10) == 100.0*10*0.0005
def test_zero_cost():
    assert BpsCostModel(bps=0.0).commission(123.0, 7) == 0.0

# --- Backward-compat: BpsCostModel also accepts 4-arg call ---
def test_bps_backward_compat_four_args():
    m = BpsCostModel(bps=5.0)
    # 4-arg call (new signature) must return same result as 2-arg call
    assert m.commission(100.0, 10, Market.NASDAQ, Side.BUY) == m.commission(100.0, 10)
    assert m.commission(100.0, 10, Market.KOSPI, Side.SELL) == m.commission(100.0, 10)

# --- KOSPI ---
def test_kospi_sell_includes_tax():
    # qty=100, price=10000 KRW
    # notional = 1_000_000
    # bps = 1.40527 (commission) + 20.0 (sell tax) = 21.40527
    # cost = 1_000_000 * 21.40527/10_000 = 2140.527
    m = MarketCostModel()
    cost = m.commission(price=10_000.0, quantity=100, market=Market.KOSPI, side=Side.SELL)
    assert abs(cost - 2140.527) < 0.001

def test_kospi_buy_no_tax():
    # qty=100, price=10000 KRW
    # notional = 1_000_000
    # bps = 1.40527 (commission only)
    # cost = 1_000_000 * 1.40527/10_000 = 140.527
    m = MarketCostModel()
    cost = m.commission(price=10_000.0, quantity=100, market=Market.KOSPI, side=Side.BUY)
    assert abs(cost - 140.527) < 0.001

def test_kospi_sell_much_greater_than_buy():
    m = MarketCostModel()
    sell = m.commission(10_000.0, 100, Market.KOSPI, Side.SELL)
    buy  = m.commission(10_000.0, 100, Market.KOSPI, Side.BUY)
    assert sell > buy * 10  # tax asymmetry: SELL is >>10x more expensive

# --- NASDAQ ---
def test_nasdaq_buy_is_25bps_notional():
    # qty=100, price=100 USD
    # notional = 10_000
    # bps = 25.0
    # cost = 10_000 * 25.0/10_000 = 25.0
    m = MarketCostModel()
    cost = m.commission(price=100.0, quantity=100, market=Market.NASDAQ, side=Side.BUY)
    assert abs(cost - 25.0) < 1e-9

def test_nasdaq_sell_adds_sec_and_taf():
    # qty=100, price=100 USD
    # notional = 10_000
    # bps = 25.0 (comm) + 0.206 (SEC sell) = 25.206
    # cost_bps = 10_000 * 25.206/10_000 = 25.206
    # FINRA TAF = min(0.000195 * 100, 9.79) = min(0.0195, 9.79) = 0.0195
    # total = 25.206 + 0.0195 = 25.2255
    m = MarketCostModel()
    cost = m.commission(price=100.0, quantity=100, market=Market.NASDAQ, side=Side.SELL)
    assert abs(cost - 25.2255) < 0.0001

def test_nasdaq_sell_greater_than_buy():
    m = MarketCostModel()
    sell = m.commission(100.0, 100, Market.NASDAQ, Side.SELL)
    buy  = m.commission(100.0, 100, Market.NASDAQ, Side.BUY)
    assert sell > buy

def test_finra_taf_cap_applied():
    # Large qty where uncapped TAF would exceed $9.79
    # 0.000195 * 51_000 = 9.945 > 9.79, so cap applies
    m = MarketCostModel()
    cost_big = m.commission(price=100.0, quantity=51_000, market=Market.NASDAQ, side=Side.SELL)
    cost_bigger = m.commission(price=100.0, quantity=100_000, market=Market.NASDAQ, side=Side.SELL)
    # TAF portion should be capped at 9.79 for both large quantities
    # difference is only from SEC fee on the notional difference, not TAF
    notional_big    = 100.0 * 51_000
    notional_bigger = 100.0 * 100_000
    bps_diff = (notional_bigger - notional_big) * 25.206 / 10_000
    assert abs((cost_bigger - cost_big) - bps_diff) < 0.01

def test_unknown_market_raises():
    import pytest
    m = MarketCostModel()
    # passing a market not in configs should raise KeyError
    with pytest.raises(KeyError):
        m.commission(100.0, 10, "UNKNOWN_MARKET", Side.BUY)
