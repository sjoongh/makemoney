from trader.execution.costs import BpsCostModel

def test_bps_cost_is_notional_times_bps():
    m = BpsCostModel(bps=5.0)  # 5bp
    assert m.commission(price=100.0, quantity=10) == 100.0*10*0.0005
def test_zero_cost():
    assert BpsCostModel(bps=0.0).commission(123.0, 7) == 0.0
