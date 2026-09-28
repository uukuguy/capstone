from __future__ import annotations

from capstone_agent.prompt_hints import build_case_prompt_decorator


def test_case_prompt_hint_only_describes_current_registered_step() -> None:
    decorate = build_case_prompt_decorator(
        application_id="pandapower-static-analysis",
        case_id="pandapower-scripted-task",
        model_id="ieee39",
        instructions=("打开 IEEE-39。", "执行交流潮流。", "筛查线路。"),
        workflows=(
            ("context.open", "topology.branch.endpoints.get"),
            ("analysis.powerflow.ac.run",),
            ("result.branches.rank",),
        ),
    )

    prompt = decorate("执行交流潮流。", 2)

    assert "pandapower-static-analysis" in prompt
    assert "case_id=pandapower-scripted-task" in prompt
    assert "model_id=ieee39" in prompt
    assert "analysis.powerflow.ac.run" in prompt
    assert "context.open" not in prompt
    assert "筛查线路。" not in prompt
    assert "执行后续步骤" in prompt
