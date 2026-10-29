from __future__ import annotations

import argparse
import json
import sys

from .bundle import load_bundle
from .runner import execute
from .transport import submit_compute_result


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="deadworlds-compute")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="Execute a Worker-issued compute bundle, upload draws, and optionally submit the compact result")
    r.add_argument("job")
    r.add_argument("--out", default="./deadworlds-compute-output")
    args = p.parse_args(argv)
    try:
        bundle = load_bundle(args.job)
        result = execute(bundle.job, args.out, transport=bundle.transport)
        if bundle.submission is not None:
            result["_submission"] = submit_compute_result(bundle.submission, result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(f"deadworlds-compute: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
