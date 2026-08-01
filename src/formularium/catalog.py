"""Loaders for the unified-theory YAML catalog (migration input, read-only).

These mirror unified-theory's engine/schema.py dataclasses. They exist only for
the one-time migration: after `formularium migrate`, the generated packages'
nodes/specs.py files are the source of truth and this module reads nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

TIERS = {"established", "derived", "conjecture"}
SOURCES = {"CODATA", "PDG", "NuFIT", "Planck", "derived", "definition", "convention"}


@dataclass
class Constant:
    name: str
    symbol: str
    value: float
    unit: str
    mass_dim: float
    tier: str = "established"
    source: str = "PDG"
    uncertainty: float | None = None
    aliases: list[str] = field(default_factory=list)
    notes: str = ""
    related_formulas: list[str] = field(default_factory=list)


@dataclass
class Quantity:
    name: str
    symbol: str
    mass_dim: float
    kind: str = "parameter"
    notes: str = ""


@dataclass
class Formula:
    id: str
    name: str
    expression: str
    symbols: list[str]
    tier: str = "established"
    provenance: str = ""
    refs: list[str] = field(default_factory=list)
    notes: str = ""
    dimensional_check: str | None = None


def _load_dir(catalog_root: Path, subdir: str) -> list[dict]:
    out = []
    for f in sorted((catalog_root / subdir).glob("*.yaml")):
        data = yaml.safe_load(f.read_text())
        if data is not None:
            out.append(data)
    return out


def load_constants(ut_root: Path) -> list[Constant]:
    return [Constant(**d) for d in _load_dir(ut_root / "catalog", "constants")]


def load_quantities(ut_root: Path) -> list[Quantity]:
    return [Quantity(**d) for d in _load_dir(ut_root / "catalog", "quantities")]


def load_formulas(ut_root: Path) -> list[Formula]:
    return [Formula(**d) for d in _load_dir(ut_root / "catalog", "formulas")]
