"""Natural-units (GeV-power) values for catalog symbols, for test-fixture generation.

Port of unified-theory engine/derive.py natural_units_values(): every constant
converted via the unit system, plus the derived intermediate couplings
(g, g' from e_em / sin2_thetaW; lambda_H from m_H, v; the nine Yukawas).
Quantities with no catalog value get a deterministic pseudo-random positive
dummy in [0.5, 2.0] so round-trip checks and non-regressible tests still have
concrete numbers to evaluate at.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

from .catalog import load_constants, load_quantities
from .units import to_natural_gev


def natural_units_values(ut_root: Path) -> dict[str, float]:
    v: dict[str, float] = {}
    for c in load_constants(ut_root):
        try:
            v[c.symbol] = to_natural_gev(float(c.value), c.unit)
        except ValueError:
            pass
    s = v["sin2_thetaW"]
    v["g"] = v["e_em"] / math.sqrt(s)  # e = g sin(theta_W)
    v["g_prime"] = v["e_em"] / math.sqrt(1 - s)  # e = g' cos(theta_W)
    v["lambda_H"] = v["m_H"] ** 2 / (2 * v["v"] ** 2)
    for f, m in [
        ("t", "m_t"),
        ("e", "m_e"),
        ("mu", "m_mu"),
        ("tau", "m_tau"),
        ("u", "m_u"),
        ("d", "m_d"),
        ("s", "m_s"),
        ("c", "m_c"),
        ("b", "m_b"),
    ]:
        v[f"y_{f}"] = math.sqrt(2) * v[m] / v["v"]
    return v


def dummy_value(symbol: str) -> float:
    """Deterministic positive dummy in [0.5, 2.0] for symbols with no catalog value."""
    h = int.from_bytes(hashlib.sha256(symbol.encode()).digest()[:8], "big")
    return 0.5 + 1.5 * (h / 2**64)


def fixture_values(ut_root: Path) -> dict[str, float]:
    """Every catalog symbol -> a concrete number (real value or deterministic dummy)."""
    vals = natural_units_values(ut_root)
    for q in load_quantities(ut_root):
        vals.setdefault(q.symbol, dummy_value(q.symbol))
    return vals
