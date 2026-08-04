# Operations: pushes, publishes, removals

**The 10-packages-per-account beta cap was lifted on 2026-08-03** — new packages push
freely and version-replacing pushes no longer need slot headroom. (The cap was
undocumented, discovered 2026-08-01 when the fleet filled all 10 slots; filed as
platform feedback 01KYZPWZ7RS3HZM5DFZMF0TJV3 + correction 01KZ1RSATP8HWG7KPKWDV730HY.
Cap-era mechanics are kept for the record in the axiom repo's `wiki/patterns.md`,
"Empirically discovered platform behavior".)

One cap-era observation is still real, just no longer a blocker: a version-replacing
`axiom push` keeps the old and new version rows **coexisting** until the old one is torn
down asynchronously (takes minutes). Poll `axiom info <pkg>@<oldver> --json` → 404 if
you need to confirm the teardown.

## Removing packages / versions

- A **pushed-only (never published) version** — even the latest/only one — is removable
  directly: `axiom remove version <pkg>@<ver> --force`.
- A **published latest** version is refused. Full retirement dance (proven on the chopper
  packages): bump version → `axiom push` the throwaway (tenant-private; `--allow-dirty`
  builds the last commit if the working tree is dirty, but local validate still reads the
  working tree — stash tracked WIP first) → `remove version <pkg>@<old> --force` (no
  longer latest) → `remove version <pkg>@<throwaway> --force` (pushed-only).
- Superseded (non-latest) published versions are removable directly — do this after each
  successful publish to keep row count at one per package.

## Push / publish runbook

```sh
# after editing a package (version already bumped):
cd ~/code/axiom/src/formularium/formularium
uv run formularium push --all --only <pkg>     # commits+pushes git, then axiom push
# platform builds from the git REMOTE at HEAD and re-runs the package's tests;
# a red test fails the push.
uv run formularium publish --all --yes         # dependency order: types -> constants+domains -> engine
```

Dependency order matters: all ten node packages (constants, the 8 domains, the engine)
`axiom import` the proto-only `formularium-types` — when the vocabulary changes, push
types first, then re-run `axiom import hamiltonjlucas/formularium-types@<ver>` +
`axiom generate` in each consumer (migrate does this automatically for generated
packages; the engine is rewired by hand). The types package's own
`messages/messages.proto` is the vocabulary's source of truth — hand-maintained, and
its `Empty` must stay in multi-line form (the CLI's proto parser cannot see
single-line `message Empty {}`, and invisible messages are dropped from consumers'
import bindings).

## Flows

Flow sources live in `flows/`. Lifecycle per change:

```sh
axiom flow validate flows/<f>.flow.yaml
axiom flow compile flows/<f>.flow.yaml      # runnable artifact id (private)
axiom flow run <artifact-id> -d '{}'        # LIVE verification — the only real oracle
axiom flow save flows/<f>.flow.yaml         # editor GRAPH document id
axiom flow publish <graph-id> --yes         # public copy; draft stays editable
```

Platform quirks these flows already route around (do not "simplify" them back):
- The engine's fan-in inputs are **JSON strings** (`toJson(value)` edge adapters +
  `json_format.Parse` in the node) because the registry rejects packages whose local
  proto embeds imported message types.
- `full-sweep` **inlines** catalog assembly: a flow facade message is not
  registry-resolvable, so the assembly flow can't be nested as a subflow by its facade.
- The report fan-in uses per-edge `adapter: { <field>: "value" }` whole-message adapters;
  compose whole-message picks (`{src_edge: alias}` without `src_path`) are rejected by
  the current compiler.
- `axiom flow publish` prompts — always pass `--yes` headless.

## Quotas to remember

2,000 invocations/day, 500 executions/day per tenant (each full-sweep run consumes several
child executions); 16 MiB payload cap (the assembled catalog is ~110 KB — fine); 30-day
execution retention (`axiom executions get <id>`).

## Invocation pacing (learned in the 2026-08-03 verification pass)

- **Parallel invoke bursts trip a per-minute 429 throttle** — 8 concurrent
  `axiom invoke` calls got mass-429'd; 2 workers with exponential backoff sweep the
  whole fleet clean (`tools/closure_sweep.py` does exactly this).
- **Scaled-to-zero nodes 502/timeout** (`context deadline exceeded`) at the default
  30s on first touch, especially when many packages cold-start at once. Warm with one
  invoke or retry once; `--timeout 60` gives cold starts room.
- **A cold first `axiom flow run` can falsely report failure** (exit 1,
  `"flow execution failed"`, no output) while the execution record shows
  FLOW_COMPLETED with every node's output present. **The execution record is the
  oracle** (`axiom executions get <id>`); an immediate re-run succeeds. Filed as
  platform feedback 01KZ5JZZVR2NHMD37GQRH7DKDJ.
