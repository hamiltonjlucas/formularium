# Catalog maintenance

How to change what the catalog asserts. The source of truth is each package's
`nodes/specs.py`; generated node bodies, tests, and protos follow from it. The original
YAML catalog (unified-theory) is retired — editing it changes nothing here.

## Edit an existing formula or constant

1. **Metadata only** (tier, provenance, refs, notes; a constant's value/uncertainty):
   edit the literal in `nodes/specs.py`. Constant *values* also appear in the generated
   per-constant tests — update the test or regenerate the package (`formularium migrate
   --only <domain|constants>`). Run `axiom test` in the package.
2. **Expression** (same input symbols): edit `expression` in `specs.py`, then
   `formularium regen-node <pkg-dir> <formula-id>`. The transcription test pins the old
   numeric expectation — regenerate the package to refresh tests, or update the expected
   value by hand. `formularium check-specs <pkg-dir>` must pass (it is the pre-commit hook).
3. **Expression with different input symbols**: the input message shape changes. Re-run
   `formularium migrate --only <domain>` (regenerates proto, node, tests), then
   `axiom generate && axiom validate --json && axiom test`.

Then: bump `version:` in `axiom.yaml` (published versions are immutable, and a deployed
node's wire contract is frozen per version — ADR-146), commit + git push, `axiom push`,
and `axiom publish` when ready. **Read `operations.md` first** — pushes at the beta cap
have a sharp edge.

## Add a formula

1. Pick the owning domain package; add a `FormulaSpec` literal to its `specs.py`
   (sympy-parseable `Eq(lhs, rhs)`, `input_symbols` = sorted RHS free symbols,
   `computes` = `str(lhs)`, honest `tier`).
2. Add the input message to `messages/messages.proto` (`message <MangledId>Input`, one
   `double` per input symbol, field names = exact catalog symbols), the node entry to
   `axiom.yaml` (`input: <MangledId>Input`, `output: FormulaResult`), the node file
   (copy a sibling; body inside the `BEGIN/END GENERATED` markers, or write it and run
   `formularium check-specs` to confirm it matches), and a numeric test.
   The generator in `src/formularium/emit.py` documents every convention
   (mangling: `W_mass` → node `WMass` → file `nodes/w_mass.py`).
3. Any new symbol must exist as a constant (constants package `specs.py`) or a quantity
   (`QUANTITIES` in the domain's `specs.py`) — the live `ValidateCatalog` node fails the
   sweep on unresolved symbols.
4. `axiom generate` → `validate` → `test` → bump version → commit/push → `axiom push`.
5. The flows pin package versions: update the `@version` pins in `flows/*.flow.yaml`,
   re-`compile`, re-run, `save` + `publish` for new public flow versions.

## Add a constant

`formularium-constants/nodes/specs.py`: add the `ConstantSpec` literal, a `Get<Symbol>`
node file + test + `axiom.yaml` entry (input `Empty`, output `ConstantSpec`). `GetCatalog`
picks it up automatically (it iterates `CONSTANTS`).

## Add a whole domain package

**Blocked by default**: the account is at the 10-package beta cap (see
`operations.md`). If a slot exists: add the domain to `src/formularium/domains.py`
(partition table + `DOMAINS`), put its formulas in the table, run
`formularium migrate --only <new-domain>`, `formularium repo sync --only <pkg>`, push.
Update `flows/*.flow.yaml` (new `GetCatalog` alias + edge + a new JSON-slice field on the
engine's `AssembleCatalogInput` — which means an engine change too).

## Verification gates (run after any change)

```sh
formularium validate --all                     # every package validate passes
formularium check-specs <changed-pkg-dir>      # specs <-> body consistency
(cd <pkg> && axiom test)                       # numeric regressions green
# after push: live sweep — the real oracle
curl -s https://api.axiomide.com/api/flows/hamiltonjlucas/formularium-full-sweep  # graph id
axiom flow run <graph_id> -d '{}' --json       # validation.passed, 0 dimension
                                               # inconsistencies, 0 unit mismatches
```
