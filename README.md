# Formularium

**A physics catalog rebuilt axiom-native**: every formula is a typed compute node, every
constant is an invokable node, and the [Axiom](https://dev.axiomide.com) packages themselves
are the source of truth. Formularium is the successor to the file-based *unified-theory*
catalog — 71 constants, 63 quantities, and 102 formulas spanning electroweak physics,
flavor, atomic physics, gravity/thermodynamics, cosmology, and quantum information, plus
discovery engines (dimensional analysis, graph structure, symbolic derivation, numeric
relation search, exhaustive synthesis, Buckingham-π).

This repository holds the **local tooling**; the catalog itself lives in the Formularium
Axiom packages, each in its own public repository:

| Package | Contents |
|---|---|
| `hamiltonjlucas/formularium-types` | shared protobuf contracts (specs, catalog, reports) |
| `hamiltonjlucas/formularium-constants` | 71 constant nodes + `GetCatalog` |
| `hamiltonjlucas/formularium-electroweak` | 11 formula nodes (W/Z masses, Higgs, Yukawa structure) |
| `hamiltonjlucas/formularium-flavor` | 17 formula nodes (Koide, Gatto, CKM, Yukawa values) |
| `hamiltonjlucas/formularium-bz-cascade` | 11 formula nodes (BZ-scale cascade relations) |
| `hamiltonjlucas/formularium-atomic` | 15 formula nodes (Bohr, Rydberg, Compton, Thomson) |
| `hamiltonjlucas/formularium-em-si` | 10 formula nodes (SI electromagnetism & thermodynamics) |
| `hamiltonjlucas/formularium-gravity-thermo` | 16 formula nodes (horizons, Planck units, entropy bounds) |
| `hamiltonjlucas/formularium-cosmology` | 16 formula nodes (FRW, dark energy, holography) |
| `hamiltonjlucas/formularium-quantum-info` | 6 formula nodes (Tsirelson, weak values) |
| `hamiltonjlucas/formularium-engine` | discovery/analysis nodes over the assembled catalog |

Every formula node **computes**: it takes the right-hand-side symbols as `double` inputs
(natural units, ħ=c=1, GeV powers) and returns a `FormulaResult`. Flows compose them into
larger computations; the engine nodes consume the assembled catalog to check dimensions,
map the relationship graph, and search for new relations.

## The `formularium` CLI

```
formularium check <unified-theory-path>     # migration pre-flight (round-trip gate)
formularium migrate <unified-theory-path>   # one-time YAML -> package-source generation
formularium repo create|sync                # public GitHub repo orchestration
formularium regen-node | check-specs        # keep node bodies consistent with specs.py
formularium validate|push|publish --all     # drive the fleet in dependency order
formularium catalog assemble | sweep run    # invoke the flows
```

After migration, the YAML catalog is retired: each package's `nodes/specs.py` is the
editable source of truth, and `formularium check-specs` (installed as a pre-commit hook)
keeps the generated node arithmetic consistent with it.

## Development

```sh
uv sync
uv run formularium check ~/science/unified-theory
```

## License

Apache-2.0. The original unified-theory catalog and this port are by the same author.
