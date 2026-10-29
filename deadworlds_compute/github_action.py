from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def _json_request(req: urllib.request.Request, timeout: int = 60) -> dict:
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} from {req.full_url}: {detail[:1500]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling {req.full_url}: {exc.reason}") from exc
    return json.loads(body) if body else {}


def github_oidc_token(audience: str = "deadworlds-compute") -> str:
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "").strip()
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "").strip()
    if not request_url or not request_token:
        raise RuntimeError("GitHub Actions OIDC environment is unavailable; workflow requires permissions: id-token: write")
    sep = "&" if "?" in request_url else "?"
    url = request_url + sep + urllib.parse.urlencode({"audience": audience})
    data = _json_request(
        urllib.request.Request(
            url,
            method="GET",
            headers={"Authorization": f"Bearer {request_token}", "Accept": "application/json"},
        )
    )
    token = str(data.get("value") or "").strip()
    if not token:
        raise RuntimeError("GitHub OIDC endpoint returned no token")
    return token


def claim_compute_bundle(base_url: str, compute_job_id: str, *, output: str | Path = "compute-bundle.json") -> Path:
    oidc = github_oidc_token()
    url = base_url.rstrip("/") + f"/compute-sandbox/{compute_job_id}/github-claim"
    data = _json_request(
        urllib.request.Request(
            url,
            data=b"{}",
            method="POST",
            headers={
                "X-Deadworlds-GitHub-OIDC": oidc,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "deadworlds-science-runner",
            },
        )
    )
    if data.get("bundle_version") != "deadworlds-compute-bundle-v0.1.0":
        raise RuntimeError(f"Forge returned an unexpected compute bundle: {data}")
    path = Path(output)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    base = os.environ.get("DEADWORLDS_FORGE_BASE", "").strip()
    job = os.environ.get("DEADWORLDS_COMPUTE_JOB_ID", "").strip()
    if not base or not job:
        raise SystemExit("DEADWORLDS_FORGE_BASE and DEADWORLDS_COMPUTE_JOB_ID are required")
    path = claim_compute_bundle(base, job)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
