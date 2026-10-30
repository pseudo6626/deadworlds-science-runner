"""Deadworlds deterministic scientific figure renderer."""

__version__ = "0.7.0"

from .render import render_figure_spec
from .validate import validate_figure_spec

__all__ = ["render_figure_spec", "validate_figure_spec", "__version__"]
