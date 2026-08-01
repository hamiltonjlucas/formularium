"""Render a formula's RHS as plain-Python arithmetic over `input.<symbol>` fields.

The generated node bodies must not depend on sympy at runtime: the whole
function vocabulary across the catalog is + - * / **, sqrt, exp, log, pi, plus
zero-argument literals (Rational, zeta(5)) which are pre-evaluated to floats
here at generation time. Output references the `math` module only.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import sympy
from sympy import Eq, Symbol, sympify


def parse_formula(expression: str) -> Eq:
    eq = sympify(expression)
    if not isinstance(eq, Eq):
        raise TypeError(f"expression is not an Eq: {expression!r}")
    return eq


def input_symbols(eq: Eq) -> list[str]:
    """The node's input fields: the RHS free symbols, sorted for determinism."""
    return sorted(str(s) for s in eq.rhs.free_symbols)


def _pre_evaluate_literals(expr: sympy.Expr) -> sympy.Expr:
    """Replace zero-argument special-function calls (zeta(5), etc.) with Floats."""
    replacements = {}
    for node in sympy.preorder_traversal(expr):
        if isinstance(node, sympy.Function) and not node.free_symbols:
            replacements[node] = sympy.Float(float(node.evalf(17)), 17)
    return expr.xreplace(replacements) if replacements else expr


def render_rhs(eq: Eq) -> str:
    """RHS as a Python expression string over `input.<symbol>` and `math.*`."""
    rhs = _pre_evaluate_literals(eq.rhs)
    # Rename free symbols to dotted names; sympy prints them verbatim.
    rhs = rhs.xreplace({s: Symbol(f"input.{s}") for s in rhs.free_symbols})
    return sympy.pycode(rhs, fully_qualified_modules=True)


def evaluate_rendered(code: str, values: dict[str, float]) -> float:
    """Evaluate a rendered expression against a plain dict of symbol values."""
    stub = SimpleNamespace(**values)
    return float(eval(code, {"__builtins__": {}, "math": math, "input": stub}))


def evaluate_sympy(eq: Eq, values: dict[str, float]) -> float:
    """Reference evaluation: substitute values into the sympy RHS directly."""
    subs = {Symbol(s): values[s] for s in (str(x) for x in eq.rhs.free_symbols)}
    return float(eq.rhs.subs(subs).evalf(17))
