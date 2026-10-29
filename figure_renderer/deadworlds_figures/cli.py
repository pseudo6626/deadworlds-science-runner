from __future__ import annotations

import argparse
import json
from pathlib import Path

from .render import render_figure_spec


def main() -> int:
    p = argparse.ArgumentParser(description="Render a Deadworlds FigureSpec v1 deterministically.")
    p.add_argument("spec", type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--allow-unpersisted", action="store_true", help="Fixture/development use only")
    args = p.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    manifest = render_figure_spec(spec, args.out, strict_provenance=not args.allow_unpersisted)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
