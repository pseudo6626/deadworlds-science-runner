from __future__ import annotations

import csv
import hashlib
import json
import re
import textwrap
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .adapters import plans_for_spec
from .plans import PlotPlan
from .schema import RENDERER_VERSION
from .styles import publication_style
from .validate import validate_figure_spec


def _safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._-")
    return name[:120] or "figure"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            clean = {k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items()}
            w.writerow(clean)


def _add_epistemic_note(fig, ax, note: str | None) -> None:
    if not note:
        return
    ax.text(
        0.0, -0.20, note, transform=ax.transAxes, ha="left", va="top",
        fontsize=7.4, wrap=True, clip_on=False,
    )


def _display_status(value: str) -> str:
    value = str(value)
    if value in {"True", "False"}:
        return value
    if "_" not in value:
        if value.isupper() and value.isalpha():
            return value.capitalize()
        return value
    text = value.replace("_", " ").lower()
    text = text.replace("sbc", "SBC").replace("psis", "PSIS").replace("abc", "ABC").replace("cv", "CV").replace(" tv ", " TV ")
    return text[:1].upper() + text[1:]


def _render_line(plan: PlotPlan, spec: dict[str, Any]):
    fig, ax = plt.subplots(figsize=(6.5, 4.2), layout="constrained")
    for s in plan.series:
        ax.plot(s.x, s.y, marker="o", label=s.label)
    ax.set_title(plan.title)
    if plan.x_label:
        ax.set_xlabel(plan.x_label)
    if plan.y_label:
        ax.set_ylabel(plan.y_label)
    ax.set_xscale(plan.x_scale)
    ax.set_yscale(plan.y_scale)
    ax.grid(axis="y", alpha=0.25)
    if len(plan.series) > 1:
        ax.legend(frameon=False)
    if spec["recipe_id"] == "m12a_trait_frequency_by_phase":
        ax.set_ylim(0.0, 1.0)
    _add_epistemic_note(fig, ax, plan.note)
    return fig


def _render_barh(plan: PlotPlan, spec: dict[str, Any]):
    labels = list(plan.series[0].x)
    n = len(labels)
    height = min(9.0, max(3.4, 0.42 * n + 1.8))
    fig, ax = plt.subplots(figsize=(7.4, height), layout="constrained")
    y = np.arange(n)
    width = 0.8 / max(1, len(plan.series))
    offsets = (np.arange(len(plan.series)) - (len(plan.series) - 1) / 2) * width
    for idx, series in enumerate(plan.series):
        if list(series.x) != labels:
            raise ValueError("barh series must share identical category labels")
        ax.barh(y + offsets[idx], series.y, height=width * 0.92, label=series.label)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_title(plan.title)
    if plan.x_label:
        ax.set_xlabel(plan.x_label)
    ax.set_xscale(plan.x_scale)
    ax.grid(axis="x", alpha=0.25)
    if len(plan.series) > 1:
        ax.legend(frameon=False)
    _add_epistemic_note(fig, ax, plan.note)
    return fig


def _render_table(plan: PlotPlan, spec: dict[str, Any]):
    n = max(1, len(plan.table_rows))
    cols = max(1, len(plan.table_columns))
    height = min(10.0, max(2.8, 0.46 * n + 1.6))
    width = min(12.0, max(7.6, 2.35 * cols))
    fig, ax = plt.subplots(figsize=(width, height), layout="constrained")
    ax.axis("off")
    ax.set_title(plan.title, pad=12)
    display_rows = []
    for row in plan.table_rows:
        shown_row = []
        for cell in row:
            shown = _display_status(str(cell))
            wrap_width = max(22, int(78 / cols))
            shown = "\n".join(textwrap.wrap(shown, width=wrap_width)) if len(shown) > wrap_width else shown
            shown_row.append(shown)
        display_rows.append(shown_row)
    table = ax.table(
        cellText=display_rows,
        colLabels=plan.table_columns,
        loc="center",
        cellLoc="left",
        colLoc="left",
        colWidths=[1.0 / cols] * cols,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.8 if cols >= 4 else 8.2)
    table.scale(1, 1.42)
    for row_index, row in enumerate(display_rows, start=1):
        line_count = max(str(cell).count("\n") + 1 for cell in row)
        if line_count > 1:
            for col_index in range(cols):
                table[(row_index, col_index)].set_height(table[(row_index, col_index)].get_height() * min(2.6, 0.8 + 0.6 * line_count))
    _add_epistemic_note(fig, ax, plan.note)
    return fig


def _render_plan(plan: PlotPlan, spec: dict[str, Any]):
    if plan.kind == "line":
        return _render_line(plan, spec)
    if plan.kind == "barh":
        return _render_barh(plan, spec)
    if plan.kind in {"status_table", "table"}:
        return _render_table(plan, spec)
    raise ValueError(f"unknown plot-plan kind: {plan.kind}")


def render_figure_spec(
    spec: dict[str, Any],
    output_dir: str | Path,
    *,
    strict_provenance: bool = True,
) -> dict[str, Any]:
    validate_figure_spec(spec, strict_provenance=strict_provenance)
    plans = plans_for_spec(spec)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    spec_path = out / "figure_spec.json"
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    requested = set(spec["outputs"])
    emitted: list[dict[str, Any]] = []
    style_profile = spec["renderer"]["style_profile"]

    with publication_style(style_profile):
        for plan in plans:
            base = _safe_name(f"{spec['figure_id']}__{plan.suffix}")
            files = []
            fig = _render_plan(plan, spec)
            for fmt in ("png", "svg", "pdf"):
                if fmt not in requested:
                    continue
                path = out / f"{base}.{fmt}"
                metadata = None
                if fmt == "png":
                    metadata = {"Software": RENDERER_VERSION}
                elif fmt == "svg":
                    metadata = {"Date": None, "Creator": RENDERER_VERSION}
                elif fmt == "pdf":
                    metadata = {"CreationDate": None, "ModDate": None, "Creator": RENDERER_VERSION, "Producer": RENDERER_VERSION}
                fig.savefig(path, format=fmt, bbox_inches="tight", metadata=metadata)
                files.append(path)
            plt.close(fig)

            if "csv" in requested and plan.csv_rows:
                path = out / f"{base}.csv"
                _write_csv(path, plan.csv_rows)
                files.append(path)

            if "json" in requested:
                path = out / f"{base}.json"
                payload = {
                    "component": plan.suffix,
                    "kind": plan.kind,
                    "title": plan.title,
                    "note": plan.note,
                    "x_label": plan.x_label,
                    "y_label": plan.y_label,
                    "x_scale": plan.x_scale,
                    "y_scale": plan.y_scale,
                    "series": [
                        {"label": s.label, "x": s.x, "y": s.y}
                        for s in plan.series
                    ],
                    "table_columns": plan.table_columns,
                    "table_rows": plan.table_rows,
                    "rows": plan.csv_rows,
                }
                path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
                files.append(path)

            emitted.append({
                "component": plan.suffix,
                "kind": plan.kind,
                "title": plan.title,
                "note": plan.note,
                "files": [
                    {"name": p.name, "bytes": p.stat().st_size, "sha256": _sha256(p)}
                    for p in files
                ],
            })

    manifest = {
        "renderer_version": RENDERER_VERSION,
        "matplotlib_version": matplotlib.__version__,
        "figure_spec_version": spec["spec_version"],
        "figure_id": spec["figure_id"],
        "recipe_id": spec["recipe_id"],
        "module_id": spec["module_id"],
        "module_version": spec["module_version"],
        "style_profile": style_profile,
        "source_kind": spec["data"]["source_kind"],
        "uncertainty": spec["uncertainty"],
        "epistemics": spec["epistemics"],
        "provenance": spec["provenance"],
        "warnings": (["interactive_html requested but v0.2 emits only the licensed static matplotlib fallback"] if "interactive_html" in requested else []),
        "scientific_rendering_policy": {
            "deterministic_rendering_only": True,
            "numeric_data_source": "FigureSpec.data.bindings only",
            "llm_numeric_plot_data_allowed": False,
            "source_precision": "NEVER_EXCEED_SOURCE",
        },
        "components": emitted,
        "spec_sha256": _sha256(spec_path),
    }
    manifest_path = out / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return manifest
