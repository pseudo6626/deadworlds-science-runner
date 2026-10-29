from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
EXPECTED_BUNDLE_VERSION = "deadworlds-compute-bundle-v0.1.0"
EXPECTED_SOURCE_RULE = "WORKER_ISSUED_IMMUTABLE_COMPUTE_JOB"
TRUSTED_FORGE_BASES = {
    "https://deadworlds-forge-sandbox.pseudonymous-cypher.workers.dev": "sandbox",
    "https://deadworlds-forge.pseudonymous-cypher.workers.dev": "production",
}
USER_AGENT = "Deadworlds-GitHub-Actions/1"


def claim_url(base: str, job_id: str) -> str:
    base = base.rstrip("/")
    environment = TRUSTED_FORGE_BASES.get(base)
    if environment is None:
        raise ValueError("untrusted Forge base")
    if environment == "sandbox":
        return f"{base}/compute-sandbox/{job_id}/github-claim"
    return f"{base}/v1/compute/jobs/{job_id}/github-claim"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--job-id", required=True)
    p.add_argument("--oidc-file", required=True)
    p.add_argument("--forge-base", required=True, choices=tuple(TRUSTED_FORGE_BASES))
    p.add_argument("--out", required=True)
    args = p.parse_args()

    if not UUID_RE.fullmatch(args.job_id):
        raise SystemExit("invalid compute job id")

    token = Path(args.oidc_file).read_text(encoding="utf-8").strip()
    if token.count(".") != 2:
        raise SystemExit("OIDC token is not a JWT")

    base = args.forge_base.rstrip("/")
    url = claim_url(base, args.job_id)
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Deadworlds-GitHub-OIDC": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise SystemExit(
            f"Forge claim HTTP {exc.code} from {base}: {detail[:2000]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"Forge claim network error from {base}: {exc.reason}"
        ) from exc

    print(f"Claimed immutable bundle from {base}.")
    payload = json.loads(raw)
    if payload.get("bundle_version") != EXPECTED_BUNDLE_VERSION:
        raise SystemExit("unexpected bundle version")
    if payload.get("compute_job_id") != args.job_id:
        raise SystemExit("bundle/job id mismatch")
    package = payload.get("package") or {}
    if package.get("sourceRule") != EXPECTED_SOURCE_RULE:
        raise SystemExit("bundle source rule mismatch")
    if not payload.get("transport", {}).get("lease_token"):
        raise SystemExit("bundle omitted lease capability")
    if not payload.get("submission", {}).get("token"):
        raise SystemExit("bundle omitted submission capability")

    out = Path(args.out)
    out.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    try:
        out.chmod(0o600)
    except OSError:
        pass
    print("Worker-issued bundle claimed and validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
