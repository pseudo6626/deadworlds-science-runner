from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
EXPECTED_BUNDLE_VERSION = "deadworlds-compute-bundle-v0.1.0"
EXPECTED_SOURCE_RULE = "WORKER_ISSUED_IMMUTABLE_COMPUTE_JOB"


def _candidate_urls(base: str, job_id: str) -> list[str]:
    base = base.rstrip("/")
    if "forge-sandbox" in base:
        return [f"{base}/compute-sandbox/{job_id}/github-claim"]
    return [f"{base}/v1/compute/jobs/{job_id}/github-claim"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--job-id", required=True)
    p.add_argument("--oidc-file", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    if not UUID_RE.fullmatch(args.job_id):
        raise SystemExit("invalid compute job id")

    token = Path(args.oidc_file).read_text(encoding="utf-8").strip()
    if token.count(".") != 2:
        raise SystemExit("OIDC token is not a JWT")

    configured = os.environ.get("DEADWORLDS_FORGE_BASES", "").strip()
    bases = [
        b.strip().rstrip("/")
        for b in (
            configured.split(";")
            if configured
            else [
                "https://deadworlds-forge-sandbox.pseudonymous-cypher.workers.dev",
                "https://deadworlds-forge.pseudonymous-cypher.workers.dev",
            ]
        )
        if b.strip()
    ]

    raw: bytes | None = None
    last_404 = ""
    for base in bases:
        for url in _candidate_urls(base, args.job_id):
            req = urllib.request.Request(
                url,
                data=b"{}",
                method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Deadworlds-GitHub-OIDC": token,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "Deadworlds-GitHub-Actions/1",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()
                print(f"Claimed immutable bundle from {base}.")
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")
                if exc.code == 404:
                    last_404 = detail
                    continue
                raise SystemExit(
                    f"Forge claim HTTP {exc.code} from {base}: {detail[:2000]}"
                ) from exc
            except urllib.error.URLError as exc:
                raise SystemExit(
                    f"Forge claim network error from {base}: {exc.reason}"
                ) from exc
        if raw is not None:
            break

    if raw is None:
        raise SystemExit(
            "Compute job was not found at any trusted Forge endpoint. "
            + last_404[:1000]
        )

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
