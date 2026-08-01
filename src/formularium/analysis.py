"""Migration pre-flight: verify every assumption the generator relies on.

Checks (all against the read-only unified-theory checkout):
  1. DOMAIN_OF covers exactly the catalog's formula ids (set equality).
  2. Every formula parses as Eq with disjoint LHS/RHS free symbols
     (forward evaluation is universally valid — never an inverse solve).
  3. The hand-authored `symbols:` list matches the sympy-derived free symbols
     (drift is reported; the generator emits the corrected list).
  4. Round-trip: the rendered plain-Python body evaluates to the same number
     as direct sympy substitution, at real catalog values (dummies for
     valueless quantities). Gate: >= 100/102 must pass mechanically.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .catalog import Formula, load_constants, load_formulas, load_quantities
from .domains import DOMAIN_OF
from .natvals import fixture_values
from .printer import (
    evaluate_rendered,
    evaluate_sympy,
    input_symbols,
    parse_formula,
    render_rhs,
)

REL_TOL = 1e-12


@dataclass
class FormulaAnalysis:
    formula: Formula
    domain: str
    eq: object
    inputs: list[str]  # RHS free symbols, sorted — the node's input fields
    computes: str  # str(eq.lhs)
    lhs_is_bare_symbol: bool
    rendered: str  # plain-Python body expression
    symbols_drift: list[str]  # differences between YAML symbols: and sympy free symbols
    roundtrip_rel_err: float | None
    roundtrip_error: str | None


def analyze(ut_root: Path) -> tuple[list[FormulaAnalysis], list[str]]:
    """Analyze every formula; return (analyses, fatal_problems)."""
    problems: list[str] = []
    formulas = load_formulas(ut_root)

    ids = {f.id for f in formulas}
    missing = ids - set(DOMAIN_OF)
    extra = set(DOMAIN_OF) - ids
    if missing:
        problems.append(f"DOMAIN_OF missing formula ids: {sorted(missing)}")
    if extra:
        problems.append(f"DOMAIN_OF has unknown formula ids: {sorted(extra)}")

    known_symbols = {c.symbol for c in load_constants(ut_root)} | {
        q.symbol for q in load_quantities(ut_root)
    }
    vals = fixture_values(ut_root)

    analyses: list[FormulaAnalysis] = []
    for f in formulas:
        try:
            eq = parse_formula(f.expression)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{f.id}: expression does not parse: {e}")
            continue

        lhs_syms = {str(s) for s in eq.lhs.free_symbols}
        rhs_syms = {str(s) for s in eq.rhs.free_symbols}
        if lhs_syms & rhs_syms:
            problems.append(f"{f.id}: LHS/RHS share symbols {sorted(lhs_syms & rhs_syms)}")
            continue

        all_syms = lhs_syms | rhs_syms
        drift = sorted(all_syms.symmetric_difference(f.symbols))
        unknown = sorted(all_syms - known_symbols)
        if unknown:
            problems.append(f"{f.id}: references symbols not in catalog: {unknown}")

        rendered = render_rhs(eq)
        rel_err: float | None = None
        rt_error: str | None = None
        try:
            got = evaluate_rendered(rendered, {s: vals[s] for s in rhs_syms})
            want = evaluate_sympy(eq, {s: vals[s] for s in rhs_syms})
            if want == 0:
                rel_err = abs(got)
            else:
                rel_err = abs(got / want - 1.0)
        except Exception as e:  # noqa: BLE001
            rt_error = f"{type(e).__name__}: {e}"

        analyses.append(
            FormulaAnalysis(
                formula=f,
                domain=DOMAIN_OF.get(f.id, "?"),
                eq=eq,
                inputs=input_symbols(eq),
                computes=str(eq.lhs),
                lhs_is_bare_symbol=len(lhs_syms) == 1
                and str(eq.lhs) in lhs_syms
                and eq.lhs.is_Symbol,
                rendered=rendered,
                symbols_drift=drift,
                roundtrip_rel_err=rel_err,
                roundtrip_error=rt_error,
            )
        )
    return analyses, problems


def roundtrip_report(ut_root: Path) -> int:
    """Print the pre-flight report; return a shell exit code (0 = gate passed)."""
    analyses, problems = analyze(ut_root)
    n = len(analyses)
    ok = [a for a in analyses if a.roundtrip_error is None and (a.roundtrip_rel_err or 0) < REL_TOL]
    drifted = [a for a in analyses if a.symbols_drift]
    non_bare = [a for a in analyses if not a.lhs_is_bare_symbol]

    print(f"formulas analyzed: {n}")
    print(f"round-trip OK (<{REL_TOL:g} rel err): {len(ok)}/{n}")
    for a in analyses:
        if a not in ok:
            detail = a.roundtrip_error or f"rel err {a.roundtrip_rel_err:g}"
            print(f"  FAIL {a.formula.id}: {detail}\n       rendered: {a.rendered}")
    print(f"symbols-list drift (will be corrected in specs): {len(drifted)}")
    for a in drifted:
        print(f"  {a.formula.id}: {a.symbols_drift}")
    print(f"non-bare-symbol LHS (labelled via computes, no direct regression): {len(non_bare)}")
    for a in non_bare:
        print(f"  {a.formula.id}: computes {a.computes}")
    if problems:
        print(f"\nFATAL problems ({len(problems)}):")
        for p in problems:
            print(f"  - {p}")
    gate = len(ok) >= 100 and not problems
    print(f"\ngate (>=100/102 round-trip, no fatal problems): {'PASSED' if gate else 'FAILED'}")
    return 0 if gate else 1
