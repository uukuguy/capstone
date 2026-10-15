import { useState, type ReactNode } from 'react'
import type { ResultProjection } from './threadProtocol'
import type { FailureEvidence } from './InferenceEvidencePanel'

function label(result: ResultProjection): string {
  return result.tables[0]?.title || result.summary[0]?.label || result.source.capabilityId
}

export default function ResultExplorer({ projections, failures, initialResultId, onClose, renderResult }: {
  projections: readonly ResultProjection[]; failures: readonly FailureEvidence[]; initialResultId?: string | null;
  onClose: () => void; renderResult: (projection: ResultProjection, tableId?: string) => ReactNode
}) {
  const [selection, setSelection] = useState(initialResultId && projections.some(item => item.resultId === initialResultId)
    ? initialResultId : projections[0]?.resultId || `failure:${failures[0]?.id}`)
  const [tables, setTables] = useState<Record<string, string>>({})
  const result = projections.find(item => item.resultId === selection)
  const failure = failures.find(item => `failure:${item.id}` === selection)
  const tableId = result?.tables.find(table => table.tableId === tables[result.resultId])?.tableId || result?.tables[0]?.tableId
  return <section className="capstone-result-explorer" aria-label="计算结果">
    <header><div><strong>计算结果</strong><small>{projections.length} 项结果 · {failures.length} 项失败记录{result ? ` · ${result.modelId}` : ''}</small></div>
      <button type="button" aria-label="关闭计算结果" onClick={onClose}>收起</button></header>
    <div className="capstone-result-explorer-layout">
      {(projections.length + failures.length > 1) && <nav aria-label="本次任务结果">
        {projections.map((item, index) => <button type="button" key={item.resultId} aria-pressed={selection === item.resultId} onClick={() => setSelection(item.resultId)}>
          <span>结果 {String(index + 1).padStart(2, '0')} · {label(item)}</span><small>{item.status === 'completed' ? '已返回' : item.status === 'partial' ? '部分结果' : '暂不可用'}</small>
        </button>)}
        {failures.map((item, index) => <button type="button" key={item.id} className="is-failed" aria-pressed={selection === `failure:${item.id}`} onClick={() => setSelection(`failure:${item.id}`)}>
          <span>失败 {String(index + 1).padStart(2, '0')} · {item.kind === 'execution' ? '执行失败' : '核验未通过'}</span><small>{item.tool || '回答核验'}</small>
        </button>)}
      </nav>}
      <div className="capstone-result-explorer-body">
        {result && <>{result.tables.length > 1 && <div className="capstone-result-table-switch" role="group" aria-label="结果表格">
          {result.tables.map(table => <button type="button" key={table.tableId} aria-pressed={tableId === table.tableId}
            onClick={() => setTables(value => ({ ...value, [result.resultId]: table.tableId }))}>{table.title} · {table.rows.length} 行</button>)}
        </div>}{renderResult(result, tableId)}</>}
        {failure && <section className="capstone-result-card is-failed" aria-label="计算结果失败记录">
          <div className="capstone-result-heading"><strong>{failure.kind === 'execution' ? '执行失败' : '核验未通过'}</strong><small>{failure.tool || '回答核验'}</small></div>
          <p>{failure.message || '该步骤未成功完成，执行记录已保留。'}</p>
          {failure.kind === 'validation' && <p>未作为已验证结论使用。</p>}
          <details><summary>技术追溯</summary><p>事件序号：{failure.sequence}</p>{failure.phase && <p>失败阶段：{failure.phase}</p>}{failure.code && <p>诊断码：{failure.code}</p>}</details>
        </section>}
      </div>
    </div>
  </section>
}
