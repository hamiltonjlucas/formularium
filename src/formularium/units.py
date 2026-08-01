"""Unit system: parse unit strings to SI base dimensions and convert to natural units.

Ported from unified-theory engine/units.py (stdlib-only). Used at generation
time to compute natural-units (GeV-power) values for node test fixtures, and
vendored into formularium-engine as nodes/units_lib.py for runtime checks.

Natural-units rule (hbar=c=k_B=eps0=1): M->+1, L->-1, T->-1, I->+1, Theta->+1, N->0.
So natural mass_dim = M - L - T + I + Theta.
"""

from __future__ import annotations

import re
from math import prod

BASES = ("M", "L", "T", "I", "Th", "N")  # mass, length, time, current, temperature, amount
_Z = (0, 0, 0, 0, 0, 0)

# unit token -> (SI scale factor, dimension over BASES)
_E = (1, 2, -2, 0, 0, 0)  # energy = M L^2 T^-2
UNITS = {
    "kg": (1.0, (1, 0, 0, 0, 0, 0)),
    "g": (1e-3, (1, 0, 0, 0, 0, 0)),
    "m": (1.0, (0, 1, 0, 0, 0, 0)),
    "km": (1e3, (0, 1, 0, 0, 0, 0)),
    "Mpc": (3.0856775815e22, (0, 1, 0, 0, 0, 0)),
    "s": (1.0, (0, 0, 1, 0, 0, 0)),
    "Hz": (1.0, (0, 0, -1, 0, 0, 0)),
    "A": (1.0, (0, 0, 0, 1, 0, 0)),
    "K": (1.0, (0, 0, 0, 0, 1, 0)),
    "mol": (1.0, (0, 0, 0, 0, 0, 1)),
    "J": (1.0, _E),
    "eV": (1.602176634e-19, _E),
    "MeV": (1.602176634e-13, _E),
    "GeV": (1.602176634e-10, _E),
    "N": (1.0, (1, 1, -2, 0, 0, 0)),
    "W": (1.0, (1, 2, -3, 0, 0, 0)),
    "Pa": (1.0, (1, -1, -2, 0, 0, 0)),
    "C": (1.0, (0, 0, 1, 1, 0, 0)),
    "V": (1.0, (1, 2, -3, -1, 0, 0)),
    "F": (1.0, (-1, -2, 4, 2, 0, 0)),
    "ohm": (1.0, (1, 2, -3, -2, 0, 0)),
    "T": (1.0, (1, 0, -2, -1, 0, 0)),  # tesla (only ever appears as J/T here)
}

_TOKEN = re.compile(r"^([A-Za-z]+)(?:\^(-?\d+))?$")


def _split_top(s: str, sep: str) -> list[str]:
    parts, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
            cur += ch
        elif ch == ")":
            depth -= 1
            cur += ch
        elif ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def _parse_product(part: str, sign: int) -> tuple[float, list[int]]:
    part = part.strip()
    if part.startswith("(") and part.endswith(")"):
        part = part[1:-1]
    scale, dim = 1.0, [0] * 6
    for tok in _split_top(part, "*"):
        tok = tok.strip()
        if not tok:
            continue
        m = _TOKEN.match(tok)
        if not m or m.group(1) not in UNITS:
            raise ValueError(f"unknown unit token: {tok!r}")
        base_scale, base_dim = UNITS[m.group(1)]
        exp = int(m.group(2)) if m.group(2) else 1
        e = sign * exp
        scale *= base_scale**e
        dim = [d + e * b for d, b in zip(dim, base_dim)]
    return scale, dim


def parse(unit: str) -> tuple[float, tuple[int, ...]]:
    """unit string -> (SI scale factor, dimension tuple over BASES)."""
    if unit in (None, "", "dimensionless"):
        return 1.0, _Z
    parts = _split_top(unit, "/")
    scale, dim = _parse_product(parts[0], +1)
    for den in parts[1:]:
        s2, d2 = _parse_product(den, -1)
        scale *= s2
        dim = [a + b for a, b in zip(dim, d2)]
    return scale, tuple(dim)


def natural_mass_dim(dim: tuple[int, ...]) -> int:
    M, L, T, I, Th, _N = dim
    return M - L - T + I + Th


# natural-units (GeV-power) conversion factor per base dimension
_C = 299792458.0
_HBAR_J = 1.054571817e-34
_GEV_J = 1.602176634e-10
_EPS0 = 8.8541878128e-12
_HBARC = 1.9732698045e-16  # GeV*m
_HBAR_GeVs = 6.582119569e-25  # GeV*s
_CHARGE = 1.0 / (_EPS0 * _HBAR_J * _C) ** 0.5  # Coulomb -> dimensionless natural charge
NAT = {
    "M": _C**2 / _GEV_J,  # kg -> GeV
    "L": 1.0 / _HBARC,  # m  -> GeV^-1
    "T": 1.0 / _HBAR_GeVs,  # s  -> GeV^-1
    "I": _CHARGE * _HBAR_GeVs,  # A  -> GeV   (A = C/s)
    "Th": 1.380649e-23 / _GEV_J,  # K  -> GeV
    "N": 1.0,  # mol-> dimensionless
}


def to_si(value: float, unit: str) -> tuple[float, tuple[int, ...]]:
    scale, dim = parse(unit)
    return value * scale, dim


def to_natural_gev(value: float, unit: str) -> float:
    """Value re-expressed in GeV^(natural mass_dim)."""
    si_value, dim = to_si(value, unit)
    return si_value * prod(NAT[b] ** e for b, e in zip(BASES, dim))
