"""Application-owned formal fallback over admitted Domain Pack projections.

Labels, values, units, ordering and calculation semantics belong to each Pack.
This renderer does not infer task completion, coverage, constraints or risk.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

from .result_projection import ResultProjection
from .task_outcome import normalize_task_outcome

if TYPE_CHECKING:
    from .harness import AdmittedAttemptAnswer


def finalize_admitted_answer(admission: 'AdmittedAttemptAnswer', *,
                            expected_identity: tuple[str, str, str, str]) -> 'AdmittedAttemptAnswer':
    """One finalization path for all runtime adapters and Domain Packs."""
    if (admission.answer_source != 'verified_results' or admission.task_outcome is None
        or admission.task_outcome.get('status') != 'partial'):
        return admission
    formal = render_admitted_result_answer(admission.result_projections,
        result_refs=admission.result_refs, evidence_refs=admission.evidence_refs,
        expected_identity=expected_identity)
    if formal is None:
        return admission
    outcome = normalize_task_outcome(admission.task_outcome)
    # The fallback itself has an admitted answer. Preserve actual lineage
    # failures elsewhere; remove only the generic missing-answer placeholder.
    placeholder = any(item['work_id'] == 'answer' and item['code'] == 'answer_admission_incomplete'
                      for item in outcome['diagnostics'])
    if placeholder:
        outcome['work'] = [item for item in outcome['work'] if item['id'] != 'answer']
        outcome['diagnostics'] = [item for item in outcome['diagnostics'] if item['work_id'] != 'answer']
    if not any(item['status'] == 'blocked' for item in outcome['work']):
        # A renderer never certifies completion of a user goal by itself.
        return replace(admission, answer=formal)
    return replace(admission, answer=formal, task_outcome=normalize_task_outcome(outcome))


def _cell(value: object) -> str:
    if value is None:
        return '未提供'
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, float):
        return f'{value:.6g}'
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', ' ')


def render_admitted_result_answer(
    documents: Sequence[Mapping[str, object]], *,
    result_refs: tuple[str, ...], evidence_refs: tuple[str, ...],
    expected_identity: tuple[str, str, str, str] | None = None,
) -> str | None:
    """Render verified facts without restoring rejected assistant prose."""
    sections = []
    identity = None
    for document in documents:
        # This internal validation hint never enters reader-facing text.
        projection = ResultProjection.from_document({key: value for key, value in document.items()
                                                     if key != '_diagram_element_ids'})
        if projection.result_ref not in result_refs or not projection.evidence_refs or not set(projection.evidence_refs).issubset(evidence_refs):
            raise ValueError('formal answer projection is not admitted')
        current = (projection.thread_id, projection.run_id, projection.turn_id, projection.attempt_id)
        if expected_identity is not None and current != expected_identity:
            raise ValueError('formal answer projection identity does not match the Attempt')
        if identity is not None and identity != current:
            raise ValueError('formal answer projection identity conflicts')
        identity = current
        if projection.status == 'unavailable' or not (projection.summary or projection.tables):
            continue
        lines = [f'**{_cell(projection.model_id)} · 分析结果 {len(sections) + 1}**']
        lines.extend(f'{_cell(metric.label)}：{_cell(metric.value)}'
                     + (f' {_cell(metric.unit)}' if metric.unit else '') for metric in projection.summary)
        for table in projection.tables:
            lines.append(f'\n**{_cell(table.title)}**\n')
            lines.append('| ' + ' | '.join(_cell(column.label) + (f' ({_cell(column.unit)})' if column.unit else '') for column in table.columns) + ' |')
            lines.append('| ' + ' | '.join('---' for _ in table.columns) + ' |')
            for row in table.rows[:10]:
                lines.append('| ' + ' | '.join(_cell(row.cells.get(column.column_id)) for column in table.columns) + ' |')
            if len(table.rows) > 10:
                lines.append(f'\n此表共有 {len(table.rows)} 行，正文显示前 10 行；完整展示请查看结果卡。')
        if projection.status == 'partial' and projection.unavailable_reason:
            lines.append(_cell(projection.unavailable_reason))
        sections.append(lines[0] + '\n\n' + '\n'.join(lines[1:]))
    return '\n\n'.join(sections) if sections else None
