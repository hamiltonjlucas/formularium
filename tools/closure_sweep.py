#!/usr/bin/env python3
"""Formularium closure sweep — live verification of every published node.

Invokes every published constant node, formula node, and GetCatalog node on the
Axiom platform and checks:
  - constants: returned spec matches nodes/specs.py (value, unit, tier, source,
    mass_dim, uncertainty)
  - formulas: replay the generated transcription test's pinned inputs against the LIVE
    node; compare to the pinned expected value (same tolerance as the local test), and
    where the local test carries a physics_sanity block, also compare to the measured
    catalog constant at its tolerance (the physics closure check)
  - GetCatalog: entry counts match specs.py

Usage (stdlib only, needs a prior `axiom login`):
    python3 tools/closure_sweep.py

Results land in ./closure_results.json (cwd); a re-run skips nodes that already
passed, so an interrupted/throttled sweep resumes where it left off — delete the
file to force a full re-sweep. First verified run: 2026-08-03, 182/182 PASS.

The fleet directory (package working trees) defaults to this repo's parent dir;
override with FORMULARIUM_FLEET. Bump VER when the fleet's published version moves.
"""

import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FLEET = Path(os.environ.get("FORMULARIUM_FLEET", Path(__file__).resolve().parents[2]))
HANDLE = "hamiltonjlucas"
VER = "0.3.0"
DOMAIN_PKGS = [
    "formularium-electroweak",
    "formularium-flavor",
    "formularium-bz-cascade",
    "formularium-atomic",
    "formularium-em-si",
    "formularium-gravity-thermo",
    "formularium-cosmology",
    "formularium-quantum-info",
]
OUT = Path.cwd() / "closure_results.json"
WORKERS = 2  # 8 workers tripped the platform's per-minute 429 throttle + cold-start 502s


def mangle(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_") if part)


def snake(pascal: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", pascal)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def load_specs(pkg: str):
    path = FLEET / pkg / "nodes" / "specs.py"
    spec = importlib.util.spec_from_file_location(f"specs_{pkg.replace('-', '_')}", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def get_field(obj: dict, name: str):
    """Fetch a proto-JSON field tolerating snake_case or camelCase."""
    if name in obj:
        return obj[name]
    camel = re.sub(r"_([a-z0-9])", lambda m: m.group(1).upper(), name)
    return obj.get(camel)


def parse_formula_test(path: Path):
    """Extract (inputs, expected, tol, catalog_value, catalog_tol) from a generated test."""
    tree = ast.parse(path.read_text())
    inputs = expected = tol = catalog_value = catalog_tol = None
    for fn in tree.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        is_transcription = fn.name.endswith("_transcription")
        is_sanity = fn.name.endswith("_physics_sanity")
        if not (is_transcription or is_sanity):
            continue
        for stmt in fn.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                tgt = stmt.targets[0]
                if isinstance(tgt, ast.Name):
                    if tgt.id == "result" and is_transcription:
                        # result = node_fn(None, SomeInput(k=v, ...)) — grab arg 2's kwargs
                        call = stmt.value
                        if (isinstance(call, ast.Call) and len(call.args) == 2
                                and isinstance(call.args[1], ast.Call)):
                            inputs = {
                                kw.arg: ast.literal_eval(kw.value)
                                for kw in call.args[1].keywords
                            }
                    elif tgt.id == "expected" and is_transcription:
                        expected = ast.literal_eval(stmt.value)
                    elif tgt.id == "catalog_value" and is_sanity:
                        catalog_value = ast.literal_eval(stmt.value)
            elif isinstance(stmt, ast.Assert):
                cmp = stmt.test
                if isinstance(cmp, ast.Compare) and isinstance(cmp.ops[0], ast.Lt):
                    if "value" in ast.unparse(cmp.left):
                        try:
                            t = ast.literal_eval(cmp.comparators[0])
                        except ValueError:
                            continue
                        if is_transcription:
                            tol = t
                        elif is_sanity:
                            catalog_tol = t
    return inputs, expected, tol, catalog_value, catalog_tol


print_lock = threading.Lock()
done_count = [0]


def invoke(ref: str, payload: dict, total: int):
    body = json.dumps(payload)
    last = None
    for attempt in range(4):
        last = subprocess.run(
            ["axiom", "invoke", ref, "--input", body, "--timeout", "60"],
            capture_output=True, text=True, timeout=120,
        )
        if last.returncode == 0:
            break
        time.sleep(5 * (2 ** attempt))  # 429/cold-start backoff: 5s, 10s, 20s
    assert last is not None
    with print_lock:
        done_count[0] += 1
        if done_count[0] % 20 == 0:
            print(f"  ... {done_count[0]}/{total} invocations done", file=sys.stderr)
    if last.returncode != 0:
        return None, last.stderr.strip()[-500:]
    try:
        return json.loads(last.stdout), None
    except json.JSONDecodeError:
        return None, f"non-JSON stdout: {last.stdout[:300]!r}"


def rel_ok(got: float, want: float, tol: float) -> bool:
    if want == 0:
        return abs(got) < tol
    return abs(got / want - 1.0) < tol


def main():
    tasks = []  # (kind, pkg, node, payload, check_ctx)

    cmod = load_specs("formularium-constants")
    for sym, spec in cmod.CONSTANTS.items():
        tasks.append(("constant", "formularium-constants", "Get" + mangle(sym), {}, spec))

    formula_specs = {}
    for pkg in DOMAIN_PKGS:
        dmod = load_specs(pkg)
        formula_specs[pkg] = dmod.FORMULAS
        for fid in dmod.FORMULAS:
            test_path = FLEET / pkg / "nodes" / f"{snake(mangle(fid))}_test.py"
            inputs, expected, tol, cat_val, cat_tol = parse_formula_test(test_path)
            if inputs is None or expected is None:
                tasks.append(("parse-fail", pkg, mangle(fid), None, fid))
                continue
            ctx = {"fid": fid, "expected": expected, "tol": tol or 1e-9,
                   "catalog_value": cat_val, "catalog_tol": cat_tol,
                   "spec": dmod.FORMULAS[fid]}
            tasks.append(("formula", pkg, mangle(fid), inputs, ctx))

    for pkg in ["formularium-constants"] + DOMAIN_PKGS:
        tasks.append(("catalog", pkg, "GetCatalog", {}, None))

    already_passed = {}
    if OUT.exists():
        for row in json.loads(OUT.read_text()):
            if row["status"] == "PASS":
                already_passed[row["ref"]] = row

    runnable = [t for t in tasks if t[0] != "parse-fail"
                and f"{HANDLE}/{t[1]}/{t[2]}@{VER}" not in already_passed]
    if already_passed:
        print(f"skipping {len(already_passed)} nodes that passed in a previous run",
              file=sys.stderr)
    total = len(runnable)
    print(f"{total} invocations queued "
          f"({sum(1 for t in tasks if t[0]=='constant')} constants, "
          f"{sum(1 for t in tasks if t[0]=='formula')} formulas, "
          f"{sum(1 for t in tasks if t[0]=='catalog')} catalogs)", file=sys.stderr)

    results = []

    def run_task(task):
        kind, pkg, node, payload, ctx = task
        ref = f"{HANDLE}/{pkg}/{node}@{VER}"
        out, err = invoke(ref, payload, total)
        row = {"kind": kind, "package": pkg, "node": node, "ref": ref}
        if out is None:
            row.update(status="INVOKE_FAIL", error=err)
            return row
        problems = []
        if kind == "constant":
            spec = ctx
            got_val = get_field(out, "value")
            if get_field(out, "symbol") != spec.symbol:
                problems.append(f"symbol: got {get_field(out, 'symbol')!r} want {spec.symbol!r}")
            if got_val is None or not rel_ok(got_val, spec.value, 1e-12):
                problems.append(f"value: got {got_val!r} want {spec.value!r}")
            if get_field(out, "unit") != spec.unit:
                problems.append(f"unit: got {get_field(out, 'unit')!r} want {spec.unit!r}")
            if get_field(out, "tier") != spec.tier:
                problems.append(f"tier: got {get_field(out, 'tier')!r} want {spec.tier!r}")
            if get_field(out, "source") != spec.source:
                problems.append(f"source: got {get_field(out, 'source')!r} want {spec.source!r}")
            got_md = get_field(out, "mass_dim") or 0
            if abs(got_md - spec.mass_dim) > 1e-12:
                problems.append(f"mass_dim: got {got_md!r} want {spec.mass_dim!r}")
            got_unc = get_field(out, "uncertainty")
            if spec.uncertainty is not None:
                if got_unc is None or not rel_ok(got_unc, spec.uncertainty, 1e-12):
                    problems.append(f"uncertainty: got {got_unc!r} want {spec.uncertainty!r}")
        elif kind == "formula":
            got_val = get_field(out, "value")
            row["value"] = got_val
            row["expected"] = ctx["expected"]
            if got_val is None or not rel_ok(got_val, ctx["expected"], ctx["tol"]):
                problems.append(f"value: got {got_val!r} want {ctx['expected']!r} (tol {ctx['tol']})")
            spec = ctx["spec"]
            for fld, want in [("formula_id", spec.id), ("computes", spec.computes), ("tier", spec.tier)]:
                got = get_field(out, fld)
                if got != want:
                    problems.append(f"{fld}: got {got!r} want {want!r}")
            if ctx["catalog_value"] is not None and got_val is not None:
                closure_ok = rel_ok(got_val, ctx["catalog_value"], ctx["catalog_tol"] or 0.25)
                row["closure"] = {"catalog_value": ctx["catalog_value"],
                                  "tol": ctx["catalog_tol"], "ok": closure_ok}
                if not closure_ok:
                    problems.append(
                        f"physics closure: got {got_val!r} vs measured "
                        f"{ctx['catalog_value']!r} (tol {ctx['catalog_tol']})")
        elif kind == "catalog":
            counts = {k: len(v) for k, v in out.items() if isinstance(v, list)}
            row["counts"] = counts
            if pkg == "formularium-constants":
                want = len(cmod.CONSTANTS)
            else:
                want = len(formula_specs[pkg])
            if want not in counts.values():
                problems.append(f"no list field with expected count {want}; got {counts}")
        row["status"] = "PASS" if not problems else "MISMATCH"
        if problems:
            row["problems"] = problems
        return row

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(run_task, runnable))
    results.extend(already_passed.values())
    for t in tasks:
        if t[0] == "parse-fail":
            results.append({"kind": "formula", "package": t[1], "node": t[2],
                            "status": "PARSE_FAIL", "error": f"could not parse test for {t[4]}"})

    OUT.write_text(json.dumps(results, indent=2))

    by_status = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)
    print(f"\n=== SWEEP SUMMARY ({len(results)} nodes) ===")
    for status in sorted(by_status):
        print(f"{status}: {len(by_status[status])}")
    for status in ("INVOKE_FAIL", "MISMATCH", "PARSE_FAIL"):
        for r in by_status.get(status, []):
            print(f"\n[{status}] {r.get('ref', r['node'])}")
            for p in r.get("problems", []):
                print(f"    {p}")
            if r.get("error"):
                print(f"    {r['error']}")
    closures = [r for r in results if r.get("closure")]
    print(f"\nphysics-closure checks run: {len(closures)} "
          f"({sum(1 for r in closures if r['closure']['ok'])} ok)")
    print(f"full results: {OUT}")
    return 0 if set(by_status) <= {"PASS"} else 1


if __name__ == "__main__":
    sys.exit(main())
