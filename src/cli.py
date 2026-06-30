"""Command-line entry point.

    candidate-transform --csv samples/candidates.csv \
        --projection samples/projection_ats.yaml --pretty

Runs the pipeline over the given sources and prints either the canonical
candidates or, if a projection config is supplied, the projected output. Output
is deterministic JSON (sorted keys) so runs are diff-able.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .pipeline import Source, run
from .projection.engine import project
from .projection.loader import load_projection
from .serialize import candidate_to_dict


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="candidate-transform")
    p.add_argument("--csv", action="append", default=[], metavar="PATH",
                   help="CSV source (repeatable)")
    p.add_argument("--resume", action="append", default=[], metavar="PATH",
                   help="resume PDF source (repeatable)")
    p.add_argument("--projection", metavar="PATH",
                   help="projection config (YAML/JSON); omit for canonical output")
    p.add_argument("--pretty", action="store_true", help="indent JSON output")
    p.add_argument("--stats", action="store_true",
                   help="print per-stage timings to stderr")
    p.add_argument("--validate", action="store_true",
                   help="print the validation report to stderr")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    sources = [Source(type="csv", path=path) for path in args.csv]
    sources += [Source(type="resume_pdf", path=path) for path in args.resume]
    if not sources:
        build_parser().error(
            "at least one source is required (e.g. --csv PATH or --resume PATH)")

    result = run(sources)

    if args.projection:
        cfg = load_projection(args.projection)
        payload: Any = [project(c, cfg) for c in result.candidates]
    else:
        payload = [candidate_to_dict(c) for c in result.candidates]

    indent = 2 if args.pretty else None
    print(json.dumps(payload, indent=indent, sort_keys=True, ensure_ascii=False))

    if args.validate:
        reports = [r.to_dict() for r in result.reports]
        print(json.dumps(reports, indent=2, sort_keys=True), file=sys.stderr)

    if args.stats:
        s = result.stats
        print(
            f"records_in={s.records_in} clusters_out={s.clusters_out} "
            f"conflicts={s.conflicts_found} timings_ms={s.stage_timings_ms}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
