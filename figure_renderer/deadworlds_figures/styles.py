from __future__ import annotations

from contextlib import contextmanager

import matplotlib as mpl

# Styling intentionally avoids fixed color assignments.  The renderer uses
# Matplotlib defaults so color is never the sole carrier of scientific meaning.
_BASE_RC = {
    "figure.dpi": 120,
    "savefig.dpi": 300,
    "font.size": 9.5,
    "axes.titlesize": 11,
    "axes.labelsize": 9.5,
    "legend.fontsize": 8.5,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
    "lines.linewidth": 1.6,
    "lines.markersize": 4.5,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.hashsalt": "deadworlds-figure-renderer-v0.9.0",
}


@contextmanager
def publication_style(style_profile: str):
    # v0.1 uses one restrained publication layout while preserving the profile
    # name in the render manifest. Domain-specific typography comes later.
    with mpl.rc_context(_BASE_RC):
        yield
