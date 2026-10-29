from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

USER_AGENT = "deadworlds-figure-renderer/0.2.0"
ALLOWED_FORGE_BASES = {
    "https://deadworlds-forge-sandbox.pseudonymous-cypher.workers.dev",
    "https://deadworlds-forge.pseudonymous-cypher.workers.dev",
}


def post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Render bundle claim failed: HTTP {exc.code}: {detail[:2000]}") from exc


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--job-id", required=True)
    p.add_argument("--oidc-file", type=Path, required=True)
    p.add_argument("--forge-base", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    if not re.fullmatch(r"[0-9a-fA-F-]{36}", args.job_id):
        raise SystemExit("Invalid Deadworlds render job id")
    forge_base = args.forge_base.rstrip("/")
    if forge_base not in ALLOWED_FORGE_BASES:
        raise SystemExit("Forge base is not in the renderer allowlist")
    token = args.oidc_file.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit("OIDC token file is empty")

    result = post_json(
        f"{forge_base}/v1/render/jobs/{args.job_id}/github-claim",
        {},
        {"Authorization": f"Bearer {token}"},
    )
    if not result.get("ok"):
        raise SystemExit(f"Forge rejected render claim: {result}")
    bundle = result.get("bundle") or result
    if bundle.get("render_job_id") != args.job_id:
        raise SystemExit("Forge returned a different render job id")
    args.out.write_text(json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    print(f"Claimed immutable render bundle {args.job_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
