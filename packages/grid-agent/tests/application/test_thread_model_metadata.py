from grid_agent.thread_model_metadata import model_display_name


def test_short_authority_title_remains_readable():
    assert model_display_name("IEEE 39-bus system", "ieee39") == "IEEE 39-bus system"


def test_authority_docstring_uses_exact_model_id_for_operator_label():
    assert model_display_name("This network " * 30, "case24_ieee_rts") == "case24_ieee_rts"
    assert model_display_name("Network description\nReferences and model notes", "case24_ieee_rts") == "case24_ieee_rts"
