"""specs.py <-> node-body consistency: `formularium check-specs` / `regen-node`.

The platform knows nothing about specs.py, so consistency between a formula's
`expression` and the generated arithmetic in its node file is enforced here, at
the git layer (repo sync installs check-specs as a pre-commit hook).
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from .emit import GENERATED_BEGIN, GENERATED_END, formula_node_name, snake
from .printer import parse_formula, render_rhs

_REGION = re.compile(
    re.escape(GENERATED_BEGIN) + r"\n(.*?)\n\s*" + re.escape(GENERATED_END), re.DOTALL
)


def _load_specs(pkg_dir: Path):
    path = pkg_dir / "nodes" / "specs.py"
    spec = importlib.util.spec_from_file_location("formularium_pkg_specs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expected_body(expression: str) -> str:
    return f"value = {render_rhs(parse_formula(expression))}"


def _node_file(pkg_dir: Path, formula_id: str) -> Path:
    return pkg_dir / "nodes" / f"{snake(formula_node_name(formula_id))}.py"


def check_specs(pkg_dir: Path) -> int:
    """Exit 0 iff every node body matches its spec. Constants packages pass trivially."""
    mod = _load_specs(pkg_dir)
    problems: list[str] = []
    for fid, spec in getattr(mod, "FORMULAS", {}).items():
        path = _node_file(pkg_dir, fid)
        if not path.exists():
            problems.append(f"{fid}: node file missing ({path.name})")
            continue
        m = _REGION.search(path.read_text())
        if not m:
            problems.append(f"{fid}: no generated region in {path.name}")
            continue
        actual = m.group(1).strip()
        expected = _expected_body(spec.expression)
        if actual != expected:
            problems.append(
                f"{fid}: node body drifted from specs.py\n"
                f"    node file: {actual}\n    expected:  {expected}\n"
                f"    (run `formularium regen-node {pkg_dir} {fid}`)"
            )
    for sym in getattr(mod, "CONSTANTS", {}):
        from .emit import constant_node_name

        path = pkg_dir / "nodes" / f"{snake(constant_node_name(sym))}.py"
        if not path.exists():
            problems.append(f"{sym}: constant node file missing ({path.name})")
    if problems:
        print(f"check-specs: {pkg_dir.name}: {len(problems)} problem(s)")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"check-specs: {pkg_dir.name}: OK")
    return 0


def regen_node(pkg_dir: Path, formula_id: str) -> int:
    mod = _load_specs(pkg_dir)
    formulas = getattr(mod, "FORMULAS", {})
    if formula_id not in formulas:
        print(f"{formula_id}: not in {pkg_dir}/nodes/specs.py FORMULAS")
        return 1
    path = _node_file(pkg_dir, formula_id)
    text = path.read_text()
    expected = _expected_body(formulas[formula_id].expression)
    new, n = _REGION.subn(f"{GENERATED_BEGIN}\n    {expected}\n    {GENERATED_END}", text, count=1)
    if n == 0:
        print(f"{formula_id}: no generated region found in {path.name}")
        return 1
    path.write_text(new)
    print(f"{formula_id}: regenerated body in {path.name}")
    print(
        "note: if input symbols changed, re-run `formularium migrate` for this package "
        "(message shapes and tests must be regenerated too)"
    )
    return 0
