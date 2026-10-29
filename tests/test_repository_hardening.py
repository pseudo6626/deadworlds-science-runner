from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.claim_bundle import TRUSTED_FORGE_BASES, claim_url

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deadworlds-compute.yml"
CONSTRAINTS = ROOT / "PRODUCTION_CONSTRAINTS.txt"
CLAIM_HELPER = ROOT / "scripts" / "claim_bundle.py"
BOOTSTRAP = ROOT / ".github" / "workflows" / "bootstrap-deadworlds.yml"


def test_claim_helper_is_present_and_environment_locked():
    assert CLAIM_HELPER.is_file()
    assert TRUSTED_FORGE_BASES == {
        "https://deadworlds-forge-sandbox.pseudonymous-cypher.workers.dev": "sandbox",
        "https://deadworlds-forge.pseudonymous-cypher.workers.dev": "production",
    }
    job = "12345678-1234-1234-1234-123456789abc"
    assert claim_url(
        "https://deadworlds-forge-sandbox.pseudonymous-cypher.workers.dev", job
    ) == f"https://deadworlds-forge-sandbox.pseudonymous-cypher.workers.dev/compute-sandbox/{job}/github-claim"
    assert claim_url(
        "https://deadworlds-forge.pseudonymous-cypher.workers.dev", job
    ) == f"https://deadworlds-forge.pseudonymous-cypher.workers.dev/v1/compute/jobs/{job}/github-claim"
    with pytest.raises(ValueError):
        claim_url("https://example.com", job)


def test_constraints_are_machine_parseable_pins():
    lines = [
        line.strip()
        for line in CONSTRAINTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert lines
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", line) for line in lines)
    assert "numpy==2.1.3" in lines
    assert "pymc==6.3.2" in lines
    assert "xarray==2025.12.0" in lines


def test_compute_workflow_has_explicit_environment_routing_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "forge_environment" in text
    assert "forge_environment must be exactly sandbox or production" in text
    assert "DEADWORLDS_FORGE_BASE:" in text
    assert "DEADWORLDS_FORGE_BASES" not in text
    assert "deadworlds-compute doctor" not in text
    assert "Bootstrap audited repository files" not in text
    assert "deadworlds-forge-sandbox.pseudonymous-cypher.workers.dev" in text
    assert "deadworlds-forge.pseudonymous-cypher.workers.dev" in text


def test_obsolete_bootstrap_workflow_is_absent():
    assert not BOOTSTRAP.exists()
