import json

from capstone_agent.kernel_capability_preparation import AuthorityModelBinding
from grid_agent.thread_binding import bind_thread_tool_catalog


def test_thread_tool_catalog_restricts_model_but_preserves_derived_context_schema(tmp_path):
    path = tmp_path / "tool-catalog.json"
    tools = [
        {"name": "grid_context_open", "capability": "context.open", "input_schema": {
            "type": "object", "properties": {"model_id": {"type": "string"}}, "required": ["model_id"]}},
        {"name": "grid_analysis_powerflow_ac", "capability": "analysis.powerflow.ac.run", "input_schema": {
            "type": "object", "properties": {"context_ref": {"type": "string", "pattern": "^context:sha256:[0-9a-f]{64}$"}}, "required": ["context_ref"]}},
        {"name": "grid_model_list", "capability": "model.list", "input_schema": {
            "type": "object", "properties": {}}},
    ]
    path.write_text(json.dumps({"schema": "grid-tool-catalog/1.0", "tools": tools}))
    bound = AuthorityModelBinding("grid", "case24_ieee_rts", "revision:sha256:" + "a" * 64,
                                  "pandapower", "context:sha256:" + "b" * 64)
    bind_thread_tool_catalog(path, bound)
    actual = json.loads(path.read_text())["tools"]
    assert actual[0]["input_schema"]["properties"]["model_id"]["enum"] == ["case24_ieee_rts"]
    assert actual[1] == tools[1]
    assert actual[2] == tools[2]
