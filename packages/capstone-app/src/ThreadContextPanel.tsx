import type { ContextChoice, InputCatalog } from './threadInput'
import {useState} from 'react'
import './threadMaterialUpload.css'

export default function ThreadContextPanel({ catalog, value, onChange, onClose, disabled,materialRefs,onMaterialRefsChange,onRemoveMaterial }: {
  catalog?: InputCatalog; value: ContextChoice; onChange: (value: ContextChoice) => void; onClose: () => void; disabled?: boolean
  materialRefs?:string[];onMaterialRefsChange?:(refs:string[])=>void;onRemoveMaterial?:(id:string)=>Promise<void>
}) {
  const selected=materialRefs??catalog?.materials.map(item=>item.material_id)??[]
  const fileCount=(catalog?.materials.length||0)+(catalog?.stored_resources?.length||0)
  const [removing,setRemoving]=useState(''),[error,setError]=useState('')
  return <section role="dialog" aria-label="本轮上下文" className="thread-settings-popover thread-input-panel">
    <div className="thread-input-heading"><strong>本轮上下文</strong><button type="button" onClick={onClose} aria-label="关闭上下文">关闭</button></div>
    <p>已发送的资料可供后续任务使用；实际读取情况见执行详情。</p>
    {!catalog && <p role="status">上下文目录暂不可用，请稍后重新打开。</p>}
    {catalog?.objects.map(object => {
      const state = value.exclude_refs.includes(object.object_id) ? 'exclude' : value.include_refs.includes(object.object_id) ? 'include' : 'auto'
      return <div className="thread-context-item" key={object.object_id}>
        <span>{object.model_id}{object.object_id === catalog.context_id ? ' · 当前' : ' · 历史'}</span>
        <details><summary>版本详情</summary><small>{object.model_revision}</small></details>
        <div role="group" aria-label={`${object.model_id} 上下文选择`}>
          {([['auto', '自动'], ['include', '包含'], ['exclude', '排除']] as const).map(([choice, label]) => <button disabled={disabled} type="button" key={choice} aria-pressed={state === choice} onClick={() => onChange({
            include_refs: [...value.include_refs.filter(ref => ref !== object.object_id), ...(choice === 'include' ? [object.object_id] : [])],
            exclude_refs: [...value.exclude_refs.filter(ref => ref !== object.object_id), ...(choice === 'exclude' ? [object.object_id] : [])],
          })}>{label}</button>)}
        </div>
      </div>
    })}
    {fileCount>0?<div className="thread-material-choices" role="group" aria-label="会话资料"><strong className="thread-context-heading">会话资料 · {fileCount} 份</strong>{catalog?.materials.map(material=><div key={material.material_id} className="thread-context-item"><label><input type="checkbox" aria-label={`读取资料 ${material.display_name}`} disabled={disabled||!!removing||!onMaterialRefsChange} checked={selected.includes(material.material_id)} onChange={event=>onMaterialRefsChange?.(event.target.checked?[...selected,material.material_id]:selected.filter(id=>id!==material.material_id))}/>{material.display_name}{material.size_bytes!==undefined&&<small> · {Math.ceil(material.size_bytes/1024)} KiB</small>}</label>{onRemoveMaterial&&<button type="button" aria-label={`移除资料 ${material.display_name}`} disabled={disabled||!!removing} onClick={async()=>{
      setRemoving(material.material_id);setError('')
      try{await onRemoveMaterial(material.material_id);if(materialRefs!==undefined)onMaterialRefsChange?.(materialRefs.filter(id=>id!==material.material_id))}
      catch{setError('资料尚未移除，请重试。')}
      finally{setRemoving('')}
    }}>{removing===material.material_id?'移除中…':'移除'}</button>}</div>)}
      {catalog?.stored_resources?.map(resource=><div className="thread-context-item" key={resource.resource_id}>
        <span>{resource.file_name}</span><small>{resource.size_bytes<1024**2?`${Math.ceil(resource.size_bytes/1024)} KiB`:`${(resource.size_bytes/1024**2).toFixed(1)} MiB`}</small>
      </div>)}
    </div>:<p>{catalog?.objects.length?'暂无可用资料。当前仅提供模型身份、版本与相关历史，不含完整网络表。':'尚无已关联资料，可上传文本资料后继续对话。'}</p>}
    {error&&<p role="alert">{error}</p>}
  </section>
}
