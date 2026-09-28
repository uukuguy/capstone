"""Application-owned prompt hints for registered provider demonstration cases."""

from __future__ import annotations

from collections.abc import Callable, Sequence


PromptDecorator = Callable[[str, int], str]


def build_case_prompt_decorator(
    *,
    application_id: str,
    case_id: str,
    model_id: str,
    instructions: Sequence[str],
    workflows: Sequence[Sequence[str]],
) -> PromptDecorator:
    """Build a bounded, current-step-only provider prompt decorator.

    The registration is trusted application input. The decorator exposes only
    the current step's primary capabilities and never includes later wording
    or expected results.
    """

    registered_instructions = tuple(instructions)
    registered_workflows = tuple(tuple(workflow) for workflow in workflows)

    def decorate(instruction: str, ordinal: int) -> str:
        index = ordinal - 1
        capabilities = (
            registered_workflows[index]
            if 0 <= index < len(registered_workflows)
            else ()
        )
        expected = (
            registered_instructions[index]
            if 0 <= index < len(registered_instructions)
            else None
        )
        expected_line = (
            "当前登记指令已匹配。"
            if expected == instruction
            else "当前输入不是登记文本；仍以当前输入为准。"
        )
        capability_line = ", ".join(capabilities) if capabilities else "未指定"
        return (
            "<registered_case_context>\n"
            f"application_id={application_id}\n"
            f"case_id={case_id}\n"
            f"model_id={model_id}\n"
            f"current_step={ordinal}\n"
            f"primary_capabilities={capability_line}\n"
            f"{expected_line}\n"
            "当前模型已由登记案例确定时，不要调用模型目录发现工具。"
            "只完成当前指令，不要执行后续步骤；只有当前指令的显式前置条件或工具错误需要时，"
            "才调用其他已发布工具。\n"
            "</registered_case_context>\n\n"
            f"{instruction}"
        )

    return decorate
