from __future__ import annotations

from capstone_agent.kernel_pi_session import _render_application_catalog_context


def test_application_catalog_context_keeps_cross_family_models_visible() -> None:
    rendered = _render_application_catalog_context({
        "schema": "capstone-thread-catalog/1",
        "default_model_id": "ieee39",
        "models": [
            {
                "model_id": "ieee39",
                "display_name": "IEEE-39",
                "implementation_family": "pandapower",
                "available": True,
            },
            {
                "model_id": "regional-six-bus",
                "display_name": "Regional six-bus",
                "implementation_family": "pypsa",
                "available": True,
            },
        ],
    })

    assert "Regional six-bus (regional-six-bus)" in rendered
    assert "family=pypsa" in rendered
    assert "Do not claim that another family has no models" in rendered
