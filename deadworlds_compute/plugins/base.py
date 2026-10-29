from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..contracts import ComputeJob


@dataclass
class PluginRun:
    draw_artifact: Path
    artifact_format: str
    sampler_diagnostics: dict[str, Any] | None
    posterior_predictive_checks: list[dict[str, Any]]
    predictive_validation: dict[str, Any] | None
    sbc: dict[str, Any] | None
    abc_diagnostics: dict[str, Any] | None = None
    parameter_summaries: list[dict[str, Any]] | None = None


class ModelPlugin(Protocol):
    name: str

    def run(self, job: ComputeJob, output_dir: Path) -> PluginRun: ...
