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
| `hamiltonjlucas/formularium-types` | 0.3.0 | **The shared protobuf vocabulary**, proto-only (`Empty`, `ConstantSpec`, `QuantitySpec`, `FormulaSpec`, `FormulaResult`, `Catalog`/`DomainCatalog`, engine report messages) — every other package imports it |
| `hamiltonjlucas/formularium-constants` | 0.3.0 | 71 `Get<Symbol>` constant nodes + `GetCatalog` |
| `hamiltonjlucas/formularium-electroweak` | 0.3.0 | 11 formula nodes (W/Z masses, Higgs VEV & quartic, gauge couplings, Yukawa structure) |
| `hamiltonjlucas/formularium-flavor` | 0.3.0 | 17 formula nodes (Koide, Gatto, CKM, mass ratios, Yukawa values) |
| `hamiltonjlucas/formularium-bz-cascade` | 0.3.0 | 11 formula nodes (BZ-scale cascade conjectures) |
| `hamiltonjlucas/formularium-atomic` | 0.3.0 | 15 formula nodes (Bohr, Rydberg, Compton, Thomson, Schwinger) |
| `hamiltonjlucas/formularium-em-si` | 0.3.0 | 10 formula nodes (SI electromagnetism & thermodynamics) |
| `hamiltonjlucas/formularium-gravity-thermo` | 0.3.0 | 16 formula nodes (Planck units, Bekenstein–Hawking, Unruh, capacity) |
| `hamiltonjlucas/formularium-cosmology` | 0.3.0 | 16 formula nodes (FRW, dark energy, holography, Casimir seesaw) |
| `hamiltonjlucas/formularium-quantum-info` | 0.3.0 | 6 formula nodes (Tsirelson bounds, weak values, gravitational impulse) |
| `hamiltonjlucas/formularium-engine` | 0.3.1 | 11 discovery/analysis nodes over the assembled `Catalog` |

The dependency graph is a single fan-out: `formularium-types` at the root, all ten
node packages importing it and nothing else — constants is an ordinary leaf like the
domains. (During the platform's since-lifted 10-package beta cap, 2026-08-01→03, the
vocabulary was temporarily merged into `formularium-constants`; versions ≤0.2.0 have
that shape.)

**Published flows**: `hamiltonjlucas/formularium-catalog-assemble` (fan out to all 9
`GetCatalog` nodes → one `Catalog`), `hamiltonjlucas/formularium-full-sweep` (catalog →
8 engines in parallel → `SweepReport`), `hamiltonjlucas/formularium-synthesize-sweep`
(pipeline/SSE streaming synthesis).

## Using it

Numeric I/O is in **each symbol's catalogued unit** — read the `unit` field on the
constant (`axiom invoke .../Get<Symbol>`) before wiring a value into a formula. The
particle-physics domains use GeV-power natural units (`M_W` → GeV), but constants whose
source data is SI stay SI (`G_N` → m³/(kg·s²), `hbar` → J·s, `Delta_A_bit` → m²), so a
formula like `planck_length` wants SI inputs, not ħ = c = 1. Input field names preserve
catalog symbol spelling (`M_W`, `G_N`, `sin2_thetaW`) — fidelity over proto naming
convention, by design.

```sh
# A constant, with uncertainty/tier/source metadata:
axiom invoke hamiltonjlucas/formularium-constants/GetMW --input '{}'
# → {"symbol":"M_W","value":80.377,"uncertainty":0.012,"unit":"GeV","tier":"established",...}

# A formula node COMPUTES (inputs = the RHS symbols, in their catalogued units):
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
`value` field, a `FormulaResult`'s number is its `value` field. Write the pick as bare
`value`: `value.value` fails at runtime (`no such key: value`) because these messages'
field named `value` shadows CEL's whole-message binding.

```yaml
# G_N, hbar, c -> Planck length, as a flow fragment (SI values, fetched live; verified)
nodes:
  - { alias: gn, package: hamiltonjlucas/formularium-constants@0.3.0, node: GetGN }
  - { alias: hb, package: hamiltonjlucas/formularium-constants@0.3.0, node: GetHbar }
  - { alias: cc, package: hamiltonjlucas/formularium-constants@0.3.0, node: GetC }
  - alias: lp
    package: hamiltonjlucas/formularium-gravity-thermo@0.3.0
    node: PlanckLength
    config: { join: { kind: AND } }
edges:
  - { from: gn, to: lp, adapter: { G_N: "value" } }
  - { from: hb, to: lp, adapter: { hbar: "value" } }
  - { from: cc, to: lp, adapter: { c: "value" } }
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
- **Read `docs/operations.md` before any push/publish** — pacing, dependency order,
  and version-removal mechanics. (The platform's 10-package beta cap, which the fleet
  filled exactly, was lifted 2026-08-03.)

Full procedures: [`docs/catalog-maintenance.md`](docs/catalog-maintenance.md) ·
[`docs/operations.md`](docs/operations.md).

### Verifying the fleet live

[`tools/closure_sweep.py`](tools/closure_sweep.py) (stdlib-only, resumable) invokes
every published node — 71 constants, 102 formulas, 9 catalogs — replaying each
formula's generated-test inputs against the live platform and checking physics
closure against the measured constants. Run it after any push, and after platform
upgrades: `python3 tools/closure_sweep.py` (results in `./closure_results.json`;
re-runs skip prior passes, so a throttled sweep resumes). First full pass:
2026-08-03, 182/182. [`flows/bh-entropy.flow.yaml`](flows/bh-entropy.flow.yaml) is
a verified worked example of composing the catalog into a multi-package calculation
(deliberately unpublished).

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
