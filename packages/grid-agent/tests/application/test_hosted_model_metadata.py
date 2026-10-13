from types import SimpleNamespace

from grid_agent.hosted import _read_model_metadata


def test_metadata_already_returned_by_open_does_not_launch_another_read():
    metadata = {"context_ref": "context:selected", "revision_ref": "revision:selected", "model": "selected", "overview": []}
    def invoke(*args):
        raise AssertionError('duplicate Authority read')
    assert _read_model_metadata(SimpleNamespace(invoke=invoke), model_id='selected',
        revision_ref='revision:selected', context_ref='context:selected', opened_metadata=metadata) == metadata


def test_model_metadata_uses_one_registered_read_and_preserves_source_identity():
    calls = []
    metadata = {"context_ref": "context:selected", "revision_ref": "revision:selected", "model": "selected",
        "counts": {"buses": 2}, "overview": [{"dataset": "network.load", "aggregates": []}]}
    def invoke(capability, arguments):
        calls.append((capability, arguments))
        return metadata
    result = _read_model_metadata(SimpleNamespace(invoke=invoke), model_id="selected",
        revision_ref="revision:selected", context_ref="context:selected")
    assert result == metadata
    assert calls == [("context.get", {"context_ref": "context:selected", "include_overview": True})]


def test_optional_metadata_failure_or_wrong_revision_does_not_block_the_bound_model():
    def failure(*args):
        raise RuntimeError("lookup failed")
    result = _read_model_metadata(SimpleNamespace(invoke=failure), model_id="selected",
        revision_ref="revision:selected", context_ref="context:selected")
    assert result["status"] == "unavailable"
    result = _read_model_metadata(SimpleNamespace(invoke=lambda *args: {
        "context_ref": "context:foreign", "revision_ref": "revision:foreign", "model": "other"}),
        model_id="selected", revision_ref="revision:selected", context_ref="context:selected")
    assert result["reason"] == "model_metadata_identity_mismatch"
