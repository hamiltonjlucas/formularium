"""`formularium migrate`: one-time YAML -> Axiom-package-source generation.

For each target package (formularium-constants + the 8 domain packages):
  1. `axiom init` if the directory doesn't exist yet.
  2. `axiom import hamiltonjlucas/formularium-types` if not yet imported.
  3. Overwrite messages/messages.proto, nodes/*.py, nodes/specs.py, tests, README, LICENSE.
  4. Rewrite the manifest's nodes/description/license (preserving imports).
  5. `axiom generate` + `axiom validate --json`.

Idempotent: re-running regenerates every generated file in place. unified-theory
is never written to.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import yaml

from .analysis import FormulaAnalysis, analyze
from .catalog import Constant, load_constants, load_quantities
from .domains import DOMAINS, package_name
from .emit import (
    SCOPE,
    SHARED_PKG,
    constant_node_name,
    emit_constant_node,
    emit_constant_test,
    emit_constants_get_catalog,
    emit_constants_get_catalog_test,
    emit_constants_proto,
    emit_constants_readme,
    emit_constants_specs,
    emit_domain_get_catalog,
    emit_domain_get_catalog_test,
    emit_domain_proto,
    emit_domain_readme,
    emit_domain_specs,
    formula_node_name,
    input_message_name,
    snake,
)
from .natvals import fixture_values, natural_units_values
from .printer import evaluate_sympy

SHARED_VERSION = "0.2.0"


def _run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def _license_text() -> str:
    return (Path(__file__).resolve().parents[2] / "LICENSE").read_text()


def _ensure_package(out_root: Path, pkg: str, report: list[str]) -> Path:
    pkg_dir = out_root / pkg
    if not (pkg_dir / "axiom.yaml").exists():
        _run(
            ["axiom", "init", f"{SCOPE}/{pkg}", "--language", "python", "--no-example-comment"],
            cwd=out_root,
        )
        report.append(f"{pkg}: scaffolded with axiom init")
    return pkg_dir


def _strip_stale_types_import(pkg_dir: Path, report: list[str]) -> None:
    """Remove any leftover import of the retired formularium-types package."""
    manifest_path = pkg_dir / "axiom.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    imports = manifest.get("imports") or []
    kept = [i for i in imports if i.get("package") != "hamiltonjlucas/formularium-types"]
    if len(kept) != len(imports):
        if kept:
            manifest["imports"] = kept
        else:
            manifest.pop("imports", None)
        manifest_path.write_text(
            yaml.dump(manifest, default_flow_style=False, sort_keys=False, width=100)
        )
        shutil.rmtree(pkg_dir / "imports" / "hamiltonjlucas-formularium-types",
                      ignore_errors=True)
        stale = pkg_dir / "gen" / "hamiltonjlucas_formularium_types_messages_pb2.py"
        stale.unlink(missing_ok=True)
        report.append(f"{pkg_dir.name}: stripped stale formularium-types import")


def _ensure_shared_import(pkg_dir: Path, report: list[str]) -> None:
    """Domain/engine packages import the shared vocabulary from formularium-constants."""
    _strip_stale_types_import(pkg_dir, report)
    manifest = yaml.safe_load((pkg_dir / "axiom.yaml").read_text())
    imports = manifest.get("imports") or []
    if not any(i.get("package") == SHARED_PKG for i in imports):
        out = _run(["axiom", "import", f"{SHARED_PKG}@{SHARED_VERSION}"], cwd=pkg_dir,
                   check=False)
        if out.returncode != 0:
            report.append(f"{pkg_dir.name}: axiom import {SHARED_PKG} FAILED: "
                          f"{(out.stdout + out.stderr).strip()[:200]}")
        else:
            report.append(f"{pkg_dir.name}: imported {SHARED_PKG}@{SHARED_VERSION}")


def _write_manifest(pkg_dir: Path, description: str, nodes: list[dict]) -> None:
    manifest = yaml.safe_load((pkg_dir / "axiom.yaml").read_text())
    manifest["description"] = description
    manifest["license"] = "Apache-2.0"
    manifest["nodes"] = nodes
    (pkg_dir / "axiom.yaml").write_text(
        yaml.dump(manifest, default_flow_style=False, sort_keys=False, width=100)
    )


def _clean_generated_nodes(pkg_dir: Path) -> None:
    """Remove previously generated node/test files (keep conftest.py and specs.py)."""
    nodes_dir = pkg_dir / "nodes"
    nodes_dir.mkdir(exist_ok=True)
    for f in nodes_dir.glob("*.py"):
        if f.name not in ("conftest.py",):
            f.unlink()


def _finish_package(pkg_dir: Path, report: list[str]) -> bool:
    gen = _run(["axiom", "generate"], cwd=pkg_dir, check=False)
    if gen.returncode != 0:
        report.append(f"{pkg_dir.name}: axiom generate FAILED\n{gen.stdout}\n{gen.stderr}")
        return False
    val = _run(["axiom", "validate", "--json"], cwd=pkg_dir, check=False)
    try:
        parsed = json.loads(val.stdout)
    except json.JSONDecodeError:
        report.append(f"{pkg_dir.name}: validate output unparseable\n{val.stdout}\n{val.stderr}")
        return False
    if not parsed.get("passed"):
        bad = [c for c in parsed["checks"] if not c["ok"]]
        report.append(f"{pkg_dir.name}: validate FAILED: {bad}")
        return False
    report.append(f"{pkg_dir.name}: validate passed")
    return True


def _generate_constants_package(
    out_root: Path, constants: list[Constant], report: list[str]
) -> bool:
    pkg = "formularium-constants"
    pkg_dir = _ensure_package(out_root, pkg, report)
    _strip_stale_types_import(pkg_dir, report)  # carries the shared vocabulary itself
    _clean_generated_nodes(pkg_dir)

    (pkg_dir / "messages" / "messages.proto").write_text(emit_constants_proto(pkg))
    (pkg_dir / "nodes" / "specs.py").write_text(emit_constants_specs(constants))
    nodes: list[dict] = []
    for c in constants:
        node = constant_node_name(c.symbol)
        stem = snake(node)
        (pkg_dir / "nodes" / f"{stem}.py").write_text(emit_constant_node(c))
        (pkg_dir / "nodes" / f"{stem}_test.py").write_text(emit_constant_test(c))
        nodes.append({"name": node, "input": "Empty", "output": "ConstantSpec"})
    (pkg_dir / "nodes" / "get_catalog.py").write_text(emit_constants_get_catalog())
    (pkg_dir / "nodes" / "get_catalog_test.py").write_text(
        emit_constants_get_catalog_test(len(constants))
    )
    nodes.append({"name": "GetCatalog", "input": "Empty", "output": "Catalog"})

    assert len({n["name"] for n in nodes}) == len(nodes), "constant node-name collision"
    _write_manifest(
        pkg_dir,
        f"Formularium physical constants: {len(constants)} invokable constant nodes "
        "(value, uncertainty, unit, natural-units mass dimension, tier, source) "
        "plus GetCatalog. Part of the Formularium axiom-native physics catalog.",
        nodes,
    )
    (pkg_dir / "README.md").write_text(emit_constants_readme(pkg, constants))
    (pkg_dir / "LICENSE").write_text(_license_text())
    return _finish_package(pkg_dir, report)


DOMAIN_DESCRIPTIONS = {
    "electroweak": "electroweak sector: W/Z masses, Higgs VEV and quartic, gauge couplings, Yukawa structure",
    "flavor": "flavor sector: Koide relation, Gatto relation, CKM structure, mass ratios, Yukawa values",
    "bz-cascade": "BZ-cascade conjectures: modular seesaw scales and the fermion-mass cascade",
    "atomic": "atomic physics: Bohr radius, Rydberg, Compton wavelength, Thomson scattering, Schwinger effect",
    "em-si": "SI electromagnetism and thermodynamics: fine structure, vacuum impedance, Stefan-Boltzmann, Wien",
    "gravity-thermo": "gravitation and horizon thermodynamics: Planck units, Bekenstein-Hawking, Unruh, capacity",
    "cosmology": "cosmology: Friedmann equations, dark energy, holographic ansatz, Casimir seesaw",
    "quantum-info": "quantum information and foundations: Tsirelson bounds, weak values, gravitational impulse",
}


def _generate_domain_package(
    out_root: Path,
    domain: str,
    analyses: list[FormulaAnalysis],
    quantities,
    real_vals: dict[str, float],
    fix_vals: dict[str, float],
    report: list[str],
) -> bool:
    pkg = package_name(domain)
    pkg_dir = _ensure_package(out_root, pkg, report)
    _clean_generated_nodes(pkg_dir)

    # quantities referenced by this domain's formulas
    ref_syms = (
        {s for a in analyses for s in a.formula.symbols}
        | {s for a in analyses for s in a.inputs}
        | {a.computes for a in analyses}
    )
    dom_quants = [q for q in quantities if q.symbol in ref_syms]

    # write the (Empty-free) proto BEFORE importing, or the importer reports a
    # collision with the previous generation's local Empty
    (pkg_dir / "messages" / "messages.proto").write_text(emit_domain_proto(pkg, analyses))
    _ensure_shared_import(pkg_dir, report)
    (pkg_dir / "nodes" / "specs.py").write_text(emit_domain_specs(domain, analyses, dom_quants))

    from .emit import emit_formula_node, emit_formula_test

    nodes: list[dict] = []
    for a in sorted(analyses, key=lambda x: x.formula.id):
        f = a.formula
        node = formula_node_name(f.id)
        stem = snake(node)
        (pkg_dir / "nodes" / f"{stem}.py").write_text(emit_formula_node(a))

        input_values = {s: fix_vals[s] for s in a.inputs}
        expected = evaluate_sympy(a.eq, input_values)
        sanity = None
        if (
            f.tier == "established"
            and a.lhs_is_bare_symbol
            and a.computes in real_vals
            and all(s in real_vals for s in a.inputs)
        ):
            sanity = real_vals[a.computes]
        (pkg_dir / "nodes" / f"{stem}_test.py").write_text(
            emit_formula_test(a, input_values, expected, sanity)
        )
        nodes.append(
            {
                "name": node,
                "input": input_message_name(f.id) if a.inputs else "Empty",
                "output": "FormulaResult",
            }
        )
    (pkg_dir / "nodes" / "get_catalog.py").write_text(emit_domain_get_catalog(domain))
    (pkg_dir / "nodes" / "get_catalog_test.py").write_text(
        emit_domain_get_catalog_test(domain, len(analyses), len(dom_quants))
    )
    nodes.append({"name": "GetCatalog", "input": "Empty", "output": "DomainCatalog"})

    assert len({n["name"] for n in nodes}) == len(nodes), f"{pkg}: node-name collision"
    _write_manifest(
        pkg_dir,
        f"Formularium {DOMAIN_DESCRIPTIONS[domain]}. {len(analyses)} formula compute nodes "
        "(natural units, GeV powers) plus GetCatalog. Part of the Formularium "
        "axiom-native physics catalog.",
        nodes,
    )
    (pkg_dir / "README.md").write_text(emit_domain_readme(pkg, domain, analyses))
    (pkg_dir / "LICENSE").write_text(_license_text())
    return _finish_package(pkg_dir, report)


def migrate(ut_root: Path, out_root: Path, only: str | None = None) -> int:
    if shutil.which("axiom") is None:
        print("axiom CLI not found on PATH")
        return 1
    analyses, problems = analyze(ut_root)
    if problems:
        print("pre-flight problems; fix before migrating:")
        for p in problems:
            print(f"  - {p}")
        return 1

    constants = load_constants(ut_root)
    quantities = load_quantities(ut_root)
    real_vals = natural_units_values(ut_root)
    fix_vals = fixture_values(ut_root)
    by_domain: dict[str, list[FormulaAnalysis]] = {d: [] for d in DOMAINS}
    for a in analyses:
        by_domain[a.domain].append(a)

    report: list[str] = []
    ok = True
    out_root.mkdir(parents=True, exist_ok=True)
    if only in (None, "constants"):
        ok &= _generate_constants_package(out_root, constants, report)
    for domain in DOMAINS:
        if only in (None, domain):
            ok &= _generate_domain_package(
                out_root, domain, by_domain[domain], quantities, real_vals, fix_vals, report
            )

    print("\n".join(report))
    print(f"\nmigrate: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1
