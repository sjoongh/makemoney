# trader/strategy/vol_target.py
"""Portfolio volatility targeting via EWMA realized vol (RiskMetrics lambda=0.94).

No-look-ahead ordering contract
--------------------------------
The scalar used to SIZE bar-t orders must reflect returns only through bar t-1.

Protocol (enforced by FusionEngine):
  1. Call scalar() BEFORE update(today_equity)  →  scalar reflects var through yesterday.
  2. Apply the scalar to size today's order.
  3. Call update(today_equity) AFTER sizing  →  today's return is ingested for tomorrow.

This guarantees: the first bar where scalar != 1.0 is bar min_obs+1, and its
scalar is based on the first min_obs daily returns ending at bar min_obs (i.e.
no same-day data was used when computing the weight for that bar).
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class PortfolioVolTargeter:
    """EWMA portfolio volatility scaler.

    Parameters
    ----------
    target_vol : float
        Annualised target volatility (default 0.12 = 12%).
    lam : float
        EWMA decay factor; 0.94 is the RiskMetrics standard.
    min_obs : int
        Number of daily returns required before the scaler leaves identity.
        Until min_obs returns are seen, scalar() returns 1.0 (identity / parity-safe).
    vol_floor : float
        Minimum annualised vol used in the denominator (avoids div-by-zero
        and prevents over-levering in very quiet markets).
    min_scalar : float
        Hard lower clip on the output scalar.
    max_scalar : float
        Hard upper clip on the output scalar (1.0 for long/cash — no leverage).
    """
    target_vol: float = 0.12
    lam: float = 0.94
    min_obs: int = 20
    vol_floor: float = 0.02
    min_scalar: float = 0.25
    max_scalar: float = 1.0

    # Internal state — not part of the public constructor signature
    _var: float = field(default=0.0, init=False, repr=False)
    _prev_equity: float | None = field(default=None, init=False, repr=False)
    _n: int = field(default=0, init=False, repr=False)

    def update(self, equity_krw: float) -> None:
        """Ingest today's equity and update the EWMA variance.

        Call AFTER scalar() has been used to size today's orders so that
        today's return does NOT influence today's sizing (no look-ahead).

        Args:
            equity_krw: Portfolio equity in KRW at close of the current bar.
        """
        if self._prev_equity is None or self._prev_equity <= 0:
            # First observation: store equity, cannot compute a return yet.
            self._prev_equity = equity_krw
            return

        r = equity_krw / self._prev_equity - 1.0
        r2 = r * r

        if self._n == 0:
            # Seed the variance with the first squared return
            self._var = r2
        else:
            self._var = self.lam * self._var + (1.0 - self.lam) * r2

        self._n += 1
        self._prev_equity = equity_krw

    def scalar(self) -> float:
        """Return the current position-size multiplier.

        Returns 1.0 (identity) until min_obs returns have been accumulated.
        Once warmed up: clip(target_vol / max(vol_ann, vol_floor), min, max).
        """
        if self._n < self.min_obs:
            return 1.0

        vol_ann = math.sqrt(self._var) * math.sqrt(252)
        effective_vol = max(vol_ann, self.vol_floor)
        raw = self.target_vol / effective_vol
        return max(self.min_scalar, min(self.max_scalar, raw))
