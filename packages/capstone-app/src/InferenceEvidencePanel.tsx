import type { ResultProjection } from './threadProtocol'

export type FailureEvidence = {
  id: string; kind: string; tool: string; message: string; code: string; phase: string; sequence: number
}
export type InferenceEvidenceProps = {
  attemptId: string; admitted: boolean; resultRefs: readonly string[]; evidenceRefs: readonly string[]
  projections: readonly ResultProjection[]; failures: readonly FailureEvidence[]
  onSelectResult?: (resultId: string) => void
}

const CAPABILITY_LABELS: Record<string, string> = {
  'analysis.powerflow.ac.run': '交流潮流', 'powerflow.ac': '交流潮流',
  'powerflow.dc': '直流潮流', 'opf.ac': '交流最优潮流', 'opf.dc': '直流最优潮流',
  'analysis.contingency.n_minus_one.run': '支路停运校核',
  'analysis.result.violations.evaluate': '约束核验', 'constraints.violations': '约束核验',
  'analysis.result.risk.rank': '越限排序', 'risk.rank': '越限排序',
  'short_circuit.iec60909': '短路电流',
  'diagnostic.run': '计算诊断',
}

function metricText(value: string | number | boolean | null): string {
  if (value === null) return '未提供'
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  return value
}

export default function InferenceEvidencePanel({ attemptId, admitted, resultRefs, evidenceRefs,
  projections, failures, onSelectResult }: InferenceEvidenceProps) {
  const results = new Set(admitted ? resultRefs : [])
  const references = new Set(admitted ? evidenceRefs : [])
  const selected = projections.filter((item) => item.attemptId === attemptId &&
    item.resultRef && results.has(item.resultRef) && item.evidenceRefs.every((ref) => references.has(ref)))
  const linkedReferences = new Set(selected.flatMap((item) => item.evidenceRefs))
  const otherReferences = [...references].filter((ref) => !linkedReferences.has(ref))
  return <section className="capstone-chat-evidence capstone-inference-evidence" aria-label="推演证据">
    <strong>推演证据</strong>
    {admitted && references.size > 0 && <p className="capstone-evidence-scope">计算引用已准入。业务判断的核验范围以计算结果为准。</p>}
    {selected.length === 0 && <p>尚未提供引用与计算结果的对应关系。</p>}
    <div className="capstone-evidence-items">
      {selected.map((item) => <details className="capstone-evidence-item" key={item.resultId}>
        <summary><span>{CAPABILITY_LABELS[item.source.capabilityId] || item.tables[0]?.title || item.source.capabilityId}</span>
          <span>{item.status === 'completed' ? '已完成' : item.status === 'partial' ? '部分结果' : '暂不可用'}</span>
          <small>{item.modelId} · 修订 {item.modelRevision.slice(-8)}</small></summary>
        <div className="capstone-evidence-item-body">
          <div className="capstone-evidence-model"><span>模型</span><strong>{item.modelId}</strong></div>
          {item.unavailableReason && <p>{item.unavailableReason}</p>}
          <dl>{item.summary.map((metric) => <div key={metric.metricId}><dt>{metric.label}</dt>
            <dd>{metricText(metric.value)}{metric.unit ? ` ${metric.unit === 'percent' ? '%' : metric.unit}` : ''}</dd></div>)}</dl>
          {onSelectResult && <button type="button" onClick={() => onSelectResult(item.resultId)}>查看对应计算结果</button>}
          <details className="capstone-evidence-trace"><summary>技术追溯 · {item.evidenceRefs.length} 条证据</summary>
            <dl><div><dt>操作</dt><dd>{item.source.capabilityId}</dd></div>
              <div><dt>领域包</dt><dd>{item.source.domainPackId}</dd></div>
              <div><dt>模型上下文</dt><dd>{item.modelContextId}</dd></div></dl>
            <code>{item.modelRevision}</code><code>{item.resultRef}</code>
            {item.evidenceRefs.map((ref) => <code key={ref}>{ref}</code>)}
          </details>
        </div>
      </details>)}
      {failures.map((item) => <section className="capstone-evidence-failure" aria-label="执行失败记录" key={item.id}>
        <strong>{item.kind === 'validation' ? '核验未通过' : '执行失败'}</strong>
        <span>{item.tool}</span><p>{item.message || '失败原因未提供'}</p>
        <details className="capstone-evidence-trace"><summary>技术追溯</summary>
          <dl><div><dt>事件序号</dt><dd>{item.sequence}</dd></div>
            {item.phase && <div><dt>阶段</dt><dd>{item.phase}</dd></div>}
            {item.code && <div><dt>诊断码</dt><dd>{item.code}</dd></div>}</dl>
        </details>
      </section>)}
    </div>
    {otherReferences.length > 0 && <details className="capstone-evidence-trace">
      <summary>其他已准入引用 · {otherReferences.length} 条</summary>
      <p>这些引用尚未关联到展示结果，保留原始标识供追溯。</p>
      {otherReferences.map((ref) => <code key={ref}>{ref}</code>)}
    </details>}
  </section>
}
