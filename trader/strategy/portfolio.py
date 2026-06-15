# trader/strategy/portfolio.py
from __future__ import annotations
from dataclasses import dataclass, field
from trader.core.events import Symbol, Market, BarEvent, FillEvent, Side

@dataclass
class FxRates:
    rates: dict[str, float]            # 통화→KRW 환율 (KRW=1.0)
    def to_krw(self, amount: float, ccy: str) -> float:
        return amount * self.rates[ccy]

def _sym_key(sym: Symbol) -> tuple[str, str]:
    """시장+티커 복합키 — 동일 티커가 다른 시장에 상장된 경우 충돌 방지."""
    return (sym.market.value, sym.ticker)

class Portfolio:
    def __init__(self, cash: dict[str, float], fx: FxRates):
        self.cash: dict[str, float] = dict(cash)
        self.fx = fx
        self._pos: dict[tuple[str, str], int] = {}          # (market, ticker) -> qty
        self._sym: dict[tuple[str, str], Symbol] = {}
        self._mark: dict[tuple[str, str], float] = {}       # (market, ticker) -> last close (해당 통화)
    def deposit(self, ccy: str, amount: float) -> None:
        self.cash[ccy] = self.cash.get(ccy, 0.0) + amount
    def position(self, sym: Symbol) -> int:
        return self._pos.get(_sym_key(sym), 0)
    def apply_fill(self, fill: FillEvent) -> None:
        key = _sym_key(fill.symbol)
        notional_krw = self.fx.to_krw(fill.price * fill.quantity, fill.currency)
        comm_krw = self.fx.to_krw(fill.commission, fill.currency)
        if fill.side == Side.BUY:
            self.cash["KRW"] = self.cash.get("KRW", 0.0) - notional_krw - comm_krw
            self._pos[key] = self._pos.get(key, 0) + fill.quantity
        else:
            self.cash["KRW"] = self.cash.get("KRW", 0.0) + notional_krw - comm_krw
            self._pos[key] = self._pos.get(key, 0) - fill.quantity
        self._sym[key] = fill.symbol
        self._mark.setdefault(key, fill.price)
    def mark(self, bar: BarEvent) -> None:
        key = _sym_key(bar.symbol)
        self._mark[key] = bar.close
        self._sym[key] = bar.symbol
    def equity_krw(self) -> float:
        eq = sum(self.fx.to_krw(amt, ccy) for ccy, amt in self.cash.items())
        for key, qty in self._pos.items():
            sym = self._sym[key]
            eq += self.fx.to_krw(qty * self._mark.get(key, 0.0), sym.currency)
        return eq

    def position_value_krw(self, sym: Symbol) -> float:
        """qty * mark * fx; returns 0 if no position or no mark."""
        key = _sym_key(sym)
        qty = self._pos.get(key, 0)
        if qty == 0:
            return 0.0
        mark = self._mark.get(key, 0.0)
        return self.fx.to_krw(qty * mark, sym.currency)

    def position_weight(self, sym: Symbol) -> float:
        """position_value_krw / equity_krw; returns 0 if equity <= 0."""
        eq = self.equity_krw()
        if eq <= 0:
            return 0.0
        return self.position_value_krw(sym) / eq

    def market_weight(self, market: Market) -> float:
        """Sum of position_value_krw for all symbols in market / equity_krw."""
        eq = self.equity_krw()
        if eq <= 0:
            return 0.0
        total = 0.0
        for key, qty in self._pos.items():
            sym = self._sym[key]
            if sym.market == market and qty != 0:
                total += self.fx.to_krw(qty * self._mark.get(key, 0.0), sym.currency)
        return total / eq

    def open_position_count(self) -> int:
        """Number of symbols with nonzero position."""
        return sum(1 for qty in self._pos.values() if qty != 0)
