"""Python mirror of the production Deadworlds FigureSpec v1 contract.

The structure below intentionally mirrors the live Forge contract named
``deadworlds-figure-spec-v1``.  It does not add scientific fields or loosen
its epistemic/provenance requirements.
"""

FIGURE_SPEC_VERSION = "deadworlds-figure-spec-v1"
VIZ_CONTRACT_VERSION = "deadworlds-viz-contract-v1"
RENDERER_VERSION = "deadworlds-figure-renderer-v0.3.0"

FIGURE_SPEC_SCHEMA = {
    "type": "object",
    "required": [
        "spec_version", "figure_id", "module_id", "module_version",
        "recipe_id", "title", "purpose", "dimensionality", "renderer",
        "data", "uncertainty", "epistemics", "outputs", "provenance",
    ],
    "properties": {
        "spec_version": {"const": FIGURE_SPEC_VERSION},
        "figure_id": {"type": "string"},
        "module_id": {"type": "string"},
        "module_version": {"type": "string"},
        "recipe_id": {"type": "string"},
        "title": {"type": "string"},
        "purpose": {"type": "string"},
        "dimensionality": {"enum": ["2d", "3d"]},
        "renderer": {
            "type": "object",
            "required": ["preferred", "fallbacks", "style_profile"],
            "properties": {
                "preferred": {"enum": ["matplotlib", "gmt_cartopy", "pyvista_vtk", "plotly"]},
                "fallbacks": {"type": "array", "items": {"type": "string"}},
                "style_profile": {"type": "string"},
            },
        },
        "data": {
            "type": "object",
            "required": ["source_kind", "bindings", "units_policy"],
            "properties": {
                "source_kind": {
                    "enum": [
                        "deterministic_diagnostic", "measured_evidence",
                        "derived_evidence", "model_posterior",
                        "illustrative_contract_test",
                    ]
                },
                "bindings": {"type": "object"},
                "units_policy": {"const": "explicit_si_or_domain_standard"},
            },
        },
        "axes": {"type": "object"},
        "uncertainty": {
            "type": "object",
            "required": ["representation", "meaning"],
            "properties": {
                "representation": {
                    "enum": [
                        "none", "errorbar", "band", "envelope",
                        "sensitivity_grid", "posterior", "categorical_status",
                    ]
                },
                "meaning": {"type": "string"},
            },
        },
        "epistemics": {
            "type": "object",
            "required": ["method_ids", "assumptions", "blocked_if", "precision_policy"],
            "properties": {
                "method_ids": {"type": "array", "items": {"type": "string"}},
                "assumptions": {"type": "array", "items": {"type": "string"}},
                "blocked_if": {"type": "array", "items": {"type": "string"}},
                "precision_policy": {"const": "never_exceed_source_precision"},
            },
        },
        "outputs": {
            "type": "array",
            "items": {"enum": ["svg", "png", "pdf", "csv", "json", "interactive_html"]},
        },
        "provenance": {
            "type": "object",
            "required": ["renderer_version_required", "module_run_id_required", "source_refs_required"],
            "properties": {
                "renderer_version_required": {"const": True},
                "module_run_id_required": {"const": True},
                "source_refs_required": {"const": True},
            },
        },
    },
}
