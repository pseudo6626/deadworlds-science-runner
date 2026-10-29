from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LineSeries:
    label: str
    x: list[Any]
    y: list[float]


@dataclass
class PlotPlan:
    suffix: str
    kind: str
    title: str
    x_label: str | None = None
    y_label: str | None = None
    series: list[LineSeries] = field(default_factory=list)
    table_columns: list[str] = field(default_factory=list)
    table_rows: list[list[str]] = field(default_factory=list)
    csv_rows: list[dict[str, Any]] = field(default_factory=list)
    note: str | None = None
    x_scale: str = "linear"
    y_scale: str = "linear"
