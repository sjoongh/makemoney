# trader/strategy/portfolio.py
from __future__ import annotations
from dataclasses import dataclass, field
from trader.core.events import Symbol, BarEvent, FillEvent, Side

@dataclass
class FxRates:
    rates: dict[str, float]            # 통화→KRW 환율 (KRW=1.0)
    def to_krw(self, amount: float, ccy: str) -> float:
        return amount * self.rates[ccy]

class Portfolio:
    def __init__(self, cash: dict[str, float], fx: FxRates):
        self.cash: dict[str, float] = dict(cash)
        self.fx = fx
        self._pos: dict[str, int] = {}          # ticker -> qty
        self._sym: dict[str, Symbol] = {}
        self._mark: dict[str, float] = {}       # ticker -> last close (해당 통화)
    def deposit(self, ccy: str, amount: float) -> None:
        self.cash[ccy] = self.cash.get(ccy, 0.0) + amount
    def position(self, sym: Symbol) -> int:
        return self._pos.get(sym.ticker, 0)
    def apply_fill(self, fill: FillEvent) -> None:
        sign = 1 if fill.side == Side.BUY else -1
        self.cash[fill.currency] = self.cash.get(fill.currency, 0.0) - sign * (fill.price*fill.quantity) - fill.commission
        self._pos[fill.symbol.ticker] = self._pos.get(fill.symbol.ticker, 0) + sign * fill.quantity
        self._sym[fill.symbol.ticker] = fill.symbol
        self._mark.setdefault(fill.symbol.ticker, fill.price)
    def mark(self, bar: BarEvent) -> None:
        self._mark[bar.symbol.ticker] = bar.close
        self._sym[bar.symbol.ticker] = bar.symbol
    def equity_krw(self) -> float:
        eq = sum(self.fx.to_krw(amt, ccy) for ccy, amt in self.cash.items())
        for tkr, qty in self._pos.items():
            sym = self._sym[tkr]
            eq += self.fx.to_krw(qty * self._mark.get(tkr, 0.0), sym.currency)
        return eq
