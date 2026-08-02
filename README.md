# Formularium

**A physics catalog rebuilt axiom-native.** Every formula is a typed compute node, every
constant is an invokable node, and the [Axiom](https://dev.axiomide.com) packages
themselves are the source of truth. Formularium is the successor to the file-based
*unified-theory* catalog: 71 constants, 63 quantities, and 102 formulas spanning
electroweak physics, flavor, atomic physics, gravity/horizon thermodynamics, cosmology,
and quantum information — plus the discovery engines (dimensional analysis, graph
structure, symbolic derivation, numeric relation search, exhaustive synthesis,
Buckingham-π) as nodes over the assembled catalog.

Everything below is **published on the Axiom marketplace** under Apache-2.0.

## The fleet

| Package | Version | Contents |
|---|---|---|
| `hamiltonjlucas/formularium-constants` | 0.2.0 | 71 `Get<Symbol>` constant nodes + `GetCatalog`, **plus the shared protobuf vocabulary** (`ConstantSpec`, `FormulaSpec`, `Catalog`, `FormulaResult`, engine report messages) that every other package imports |
| `hamiltonjlucas/formularium-electroweak` | 0.2.0 | 11 formula nodes (W/Z masses, Higgs VEV & quartic, gauge couplings, Yukawa structure) |
| `hamiltonjlucas/formularium-flavor` | 0.2.0 | 17 formula nodes (Koide, Gatto, CKM, mass ratios, Yukawa values) |
| `hamiltonjlucas/formularium-bz-cascade` | 0.2.0 | 11 formula nodes (BZ-scale cascade conjectures) |
| `hamiltonjlucas/formularium-atomic` | 0.2.0 | 15 formula nodes (Bohr, Rydberg, Compton, Thomson, Schwinger) |
| `hamiltonjlucas/formularium-em-si` | 0.2.0 | 10 formula nodes (SI electromagnetism & thermodynamics) |
| `hamiltonjlucas/formularium-gravity-thermo` | 0.2.0 | 16 formula nodes (Planck units, Bekenstein–Hawking, Unruh, capacity) |
| `hamiltonjlucas/formularium-cosmology` | 0.2.0 | 16 formula nodes (FRW, dark energy, holography, Casimir seesaw) |
| `hamiltonjlucas/formularium-quantum-info` | 0.2.0 | 6 formula nodes (Tsirelson bounds, weak values, gravitational impulse) |
| `hamiltonjlucas/formularium-engine` | 0.1.0 | 11 discovery/analysis nodes over the assembled `Catalog` |

**Published flows**: `hamiltonjlucas/formularium-catalog-assemble` (fan out to all 9
`GetCatalog` nodes → one `Catalog`), `hamiltonjlucas/formularium-full-sweep` (catalog →
8 engines in parallel → `SweepReport`), `hamiltonjlucas/formularium-synthesize-sweep`
(pipeline/SSE streaming synthesis).

## Using it

All numeric I/O is in **natural units** (ħ = c = k_B = 1, GeV powers). Input field names
preserve catalog symbol spelling (`M_W`, `G_N`, `sin2_thetaW`) — fidelity over proto
naming convention, by design.

```sh
# A constant, with uncertainty/tier/source metadata:
axiom invoke hamiltonjlucas/formularium-constants/GetMW --input '{}'
# → {"symbol":"M_W","value":80.377,"uncertainty":0.012,"unit":"GeV","tier":"established",...}

# A formula node COMPUTES (inputs = the RHS symbols, natural units):
axiom invoke hamiltonjlucas/formularium-electroweak/WMass --input '{"g":0.6529,"v":246.21965}'
# → {"value":80.378,"formula_id":"W_mass","computes":"M_W","tier":"established"}

# Resolve a published flow's runnable graph id by name, then run it:
curl -s https://api.axiomide.com/api/flows/hamiltonjlucas/formularium-full-sweep
axiom flow run <graph_id> -d '{}'          # → SweepReport (validation, dimensions, units,
                                           #   graph, structure, derive, discover, buckingham)

# Streaming synthesis (pipeline flow): input = assembled catalog + shard + wall budget.
axiom flow run <catalog_assemble_graph_id> -d '{}' --json  # capture .output as CATALOG
# request: {"catalog": CATALOG, "shard_index":0, "shard_count":1, "max_wall_ms":60000}
axiom flow run <synthesize_graph_id> --input-file request.json
```

Discovery of any node's exact schema: `axiom inspect node hamiltonjlucas/<pkg>/<Node>` or
each package's README (formula table with `computes` column).

### Composing formulas into new flows

Formula nodes chain through ordinary edge adapters — a `ConstantSpec`'s number is its
`value` field, a `FormulaResult`'s number is its `value` field:

```yaml
# G_N -> Planck length -> horizon entropy, as a flow fragment
nodes:
  - { alias: gn, package: hamiltonjlucas/formularium-constants@0.2.0, node: GetGN }
  - { alias: lp, package: hamiltonjlucas/formularium-gravity-thermo@0.2.0, node: PlanckLength }
edges:
  - { from: gn, to: lp, adapter: { G_N: "value.value", hbar: "1.0", c: "1.0" } }
```

## Maintaining the catalog (the source-of-truth workflow)

The machine-readable source of truth is each package's **`nodes/specs.py`**
(`FormulaSpec`/`ConstantSpec`/`QuantitySpec` literals). The YAML catalog it was migrated
from is retired — do not edit unified-theory expecting Formularium to change.

- **Metadata edit** (tier, provenance, notes, value/uncertainty): edit `specs.py`, run
  `axiom test`, commit+push git, `axiom push`. Publishing the change publicly needs a
  version bump (publish is immutable).
- **Expression edit**: edit `expression` in `specs.py`, then
  `formularium regen-node <pkg-dir> <formula-id>` re-renders the node's arithmetic;
  `formularium check-specs` (installed as a pre-commit hook by `formularium repo sync`)
  blocks commits where body and spec drifted. If the RHS symbols changed, re-run the
  generator for that package instead (message shapes + tests must follow).
- **Read `docs/operations.md` before any push/publish** — the platform's 10-package
  beta cap has sharp operational consequences (the fleet fills all 10 slots).

Full procedures: [`docs/catalog-maintenance.md`](docs/catalog-maintenance.md) ·
[`docs/operations.md`](docs/operations.md).

## The `formularium` CLI (this repo)

```
formularium check [ut-path]            # migration pre-flight (round-trip gate) — historical
formularium migrate [ut-path] [--only] # YAML -> package-source generation (idempotent)
formularium repo sync [--only]         # gh repos, https/ssh origins, pre-commit hooks
formularium check-specs <pkg-dir>      # verify node bodies match specs.py
formularium regen-node <pkg-dir> <id>  # re-render one node body from its spec
formularium validate --all             # axiom validate across the fleet
formularium push --all [--only pkg]    # git commit+push, then axiom push, dependency order
formularium publish --all --yes        # axiom publish, dependency order
```

Local layout: package working trees live at `~/code/axiom/src/formularium/<pkg>/`, one
public GitHub repo each (https fetch / ssh push). Shared venv for the whole fleet:
`~/code/axiom/.venv-formularium` (grpcio-tools, protobuf, pytest, sympy, networkx,
mpmath). Flows live in [`flows/`](flows/).

## Development

```sh
uv sync
uv run formularium validate --all
```

## Provenance & license

Migrated 2026-08-01/02 from `~/science/unified-theory` (which remains intact; its
investigations and Streamlit UI were deliberately not ported). Two of its 63 quantities
are referenced by no formula and therefore have no Formularium home. The engines preserve
the original honesty rules: synthesized relations inherit the weakest parent tier;
ħ/c/k_B are never eliminated; discovery scores against measurement uncertainty with
look-elsewhere accounting. Apache-2.0.
