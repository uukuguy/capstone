"""Parent report for a task that keeps ordinary work and one domain node."""
from collections.abc import Mapping

_BUSINESS = frozenset({'business_read', 'business_execute'})
_LIMIT = '节点回执中的失败、未完成和缺失数值保持为限制，不能改写成计算结果。'


def goal_heading(goals: object, *, business: bool, fallback: str) -> str:
    """Use the goal's own excerpt. Do not invent a title from the instruction."""
    if not isinstance(goals, list):
        return fallback
    for goal in goals:
        if not isinstance(goal, Mapping):
            continue
        if (goal.get('operation') in _BUSINESS) != business:
            continue
        excerpt = goal.get('instruction_excerpt')
        if isinstance(excerpt, str) and excerpt.strip():
            return excerpt.strip()[:256]
    return fallback


def assemble_domain_report(parent_text: str, node_text: str, *,
                           parent_title: str = '任务说明', node_title: str = '领域计算') -> str:
    """Join the parent draft and the node receipt. Do not recalculate either."""
    parent = parent_text.strip() or '这项说明没有形成正文。'
    node = node_text.strip() or '领域计算没有形成回执。'
    return f'{parent_title}\n\n{parent}\n\n{node_title}\n\n{node}\n\n{_LIMIT}\n'


def domain_execution_record(family: str, execution: Mapping[str, object] | None) -> dict:
    """Persist a handoff. Public events keep the role, not the two texts."""
    record = {'implementation_family': family}
    if not isinstance(execution, Mapping):
        return record
    role = execution.get('role')
    if isinstance(role, str) and role in {'node', 'report'}:
        record['role'] = role
    for key in ('parent_text', 'node_text'):
        value = execution.get(key)
        if isinstance(value, str) and value.strip():
            record[key] = value[:12000]
    return record
