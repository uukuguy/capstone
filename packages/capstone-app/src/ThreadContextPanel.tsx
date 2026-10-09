import type { ContextChoice, InputCatalog } from './threadInput'

export default function ThreadContextPanel({ catalog, value, onChange, onClose }: {
  catalog?: InputCatalog; value: ContextChoice; onChange: (value: ContextChoice) => void; onClose: () => void
}) {
  return <section role="dialog" aria-label="本轮上下文" className="thread-settings-popover thread-input-panel">
    <div className="thread-input-heading"><strong>本轮上下文</strong><button type="button" onClick={onClose} aria-label="关闭上下文">关闭</button></div>
    <p>候选资料与本轮选择。实际采用的内容将在任务详情中记录。</p>
    {!catalog && <p role="status">上下文目录暂不可用，请稍后重新打开。</p>}
    {catalog?.objects.map(object => {
      const state = value.exclude_refs.includes(object.object_id) ? 'exclude' : value.include_refs.includes(object.object_id) ? 'include' : 'auto'
      return <div className="thread-context-item" key={object.object_id}>
        <span>{object.model_id}{object.object_id === catalog.context_id ? ' · 当前' : ' · 历史'}</span>
        <details><summary>版本详情</summary><small>{object.model_revision}</small></details>
        <div role="group" aria-label={`${object.model_id} 上下文选择`}>
          {([['auto', '自动'], ['include', '包含'], ['exclude', '排除']] as const).map(([choice, label]) => <button type="button" key={choice} aria-pressed={state === choice} onClick={() => onChange({
            include_refs: [...value.include_refs.filter(ref => ref !== object.object_id), ...(choice === 'include' ? [object.object_id] : [])],
            exclude_refs: [...value.exclude_refs.filter(ref => ref !== object.object_id), ...(choice === 'exclude' ? [object.object_id] : [])],
          })}>{label}</button>)}
        </div>
      </div>
    })}
    <p>暂无可用资料。当前仅提供模型身份、版本与相关历史，不含完整网络表。</p>
  </section>
}
