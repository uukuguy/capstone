import { useState } from 'react'
import type { ResultProjection } from './threadProtocol'
import type { TaskResultCollection } from './taskResultCollections'
import { ResultProjectionCard } from './CapstoneAssistantThread'
import AnswerDetailSheet from './AnswerDetailSheet'

export default function TaskResultWorkspace({collection, onFocusElement}: {collection: TaskResultCollection; onFocusElement?: (result: ResultProjection, elementId: string) => boolean | void}) {
  const [selected, setSelected] = useState(collection.results[0]?.resultId)
  const [inspect, setInspect] = useState(false)
  const groups = new Map<string, {title: string; results: ResultProjection[]}>()
  for (const result of collection.results) {
    const view = result.presentation!
    const key = JSON.stringify([result.source.domainPackId, result.modelContextId, view.groupId])
    const group = groups.get(key) || {title:view.groupTitle,results:[]}
    group.results.push(result)
    groups.set(key, group)
  }
  const result = collection.results.find(item => item.resultId === selected) || collection.results[0]
  return <section className="task-result-workspace" aria-label={collection.title}>
    <header><h3>{collection.title}</h3><span>{groups.size} 组 · {collection.results.length} 项分析结果</span></header>
    <nav aria-label="本次指令分析对象">{[...groups.entries()].map(([id, group]) => <details key={id} open={group.results.some(item => item.resultId === result?.resultId)}>
      <summary>{group.title}<small>{group.results[0].modelId} · {group.results.length} 项</small></summary>
      <div>{group.results.map(item => <button key={item.resultId} type="button" aria-pressed={item.resultId === result?.resultId} onClick={() => setSelected(item.resultId)}>
        {item.tables[0]?.title || item.summary[0]?.label || item.source.capabilityId}
        {item.status === 'partial' && <small>部分结果</small>}
      </button>)}</div>
    </details>)}</nav>
    {result && <><div className="task-result-workspace-actions"><span>{result.modelId} · 修订 {result.modelRevision.slice(-8)}</span><button type="button" onClick={() => setInspect(true)}>查看依据</button></div>
      <ResultProjectionCard key={result.resultId} projection={result} onFocusElement={onFocusElement} />
      {inspect && <AnswerDetailSheet title="结果依据" answerLabel={collection.title} onClose={() => setInspect(false)}><dl><dt>所属指令</dt><dd>{result.attemptId}</dd><dt>操作</dt><dd>{result.source.capabilityId}</dd><dt>模型版本</dt><dd>{result.modelRevision}</dd></dl><p>以下引用来自本次执行已接纳的计算结果与证据。</p><code>{result.resultRef}</code>{result.evidenceRefs.map(ref => <p key={ref}><code>{ref}</code></p>)}</AnswerDetailSheet>}
    </>}
  </section>
}
