"""The `formularium` CLI: migration generator, repo orchestration, fleet driving."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_OUT = Path.home() / "code" / "axiom" / "src" / "formularium"
DEFAULT_UT = Path.home() / "science" / "unified-theory"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="formularium", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    chk = sub.add_parser("check", help="migration pre-flight: round-trip + table checks")
    chk.add_argument("ut_root", type=Path, nargs="?", default=DEFAULT_UT)

    mig = sub.add_parser("migrate", help="one-time YAML -> package-source generation")
    mig.add_argument("ut_root", type=Path, nargs="?", default=DEFAULT_UT)
    mig.add_argument("--out", type=Path, default=DEFAULT_OUT)
    mig.add_argument("--only", help="constants or a domain name (e.g. electroweak)")

    rep = sub.add_parser("repo", help="GitHub repo orchestration")
    rep.add_argument("action", choices=["sync"])
    rep.add_argument("--out", type=Path, default=DEFAULT_OUT)
    rep.add_argument("--only")

    cs = sub.add_parser("check-specs", help="verify node bodies match nodes/specs.py")
    cs.add_argument("pkg_dir", type=Path)

    rn = sub.add_parser("regen-node", help="re-render a node body from its spec expression")
    rn.add_argument("pkg_dir", type=Path)
    rn.add_argument("formula_id")

    for name, help_ in [
        ("validate", "axiom validate --json across all packages"),
        ("push", "git commit+push then axiom push, in dependency order"),
        ("publish", "axiom publish all packages, in dependency order"),
    ]:
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--all", action="store_true", required=True)
        sp.add_argument("--out", type=Path, default=DEFAULT_OUT)
        if name == "push":
            sp.add_argument("--only")
        if name == "publish":
            sp.add_argument("--yes", action="store_true")

    args = p.parse_args(argv)

    if args.cmd == "check":
        from .analysis import roundtrip_report

        return roundtrip_report(args.ut_root.expanduser().resolve())
    if args.cmd == "migrate":
        from .migrate import migrate

        return migrate(
            args.ut_root.expanduser().resolve(), args.out.expanduser().resolve(), args.only
        )
    if args.cmd == "repo":
        from .fleet import repo_sync

        return repo_sync(args.out.expanduser().resolve(), args.only)
    if args.cmd == "check-specs":
        from .regen import check_specs

        return check_specs(args.pkg_dir.expanduser().resolve())
    if args.cmd == "regen-node":
        from .regen import regen_node

        return regen_node(args.pkg_dir.expanduser().resolve(), args.formula_id)
    if args.cmd == "validate":
        from .fleet import validate_all

        return validate_all(args.out.expanduser().resolve())
    if args.cmd == "push":
        from .fleet import push_all

        return push_all(args.out.expanduser().resolve(), getattr(args, "only", None))
    if args.cmd == "publish":
        from .fleet import publish_all

        return publish_all(args.out.expanduser().resolve())
    return 2


if __name__ == "__main__":
    sys.exit(main())
