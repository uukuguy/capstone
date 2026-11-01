import {FileCheck2} from 'lucide-react'
import {groupNativeArtifacts,nativeArtifactVersions,nativeArtifactSavedTime,type NativeArtifact} from './nativeArtifacts'

/** Uses persisted purposes. A primary output is not automatically accepted delivery. */
export default function InstructionFiles({files,onOpen}:{files:NativeArtifact[];onOpen:(file:NativeArtifact)=>void}) {
  const versions=nativeArtifactVersions(files)
  const groups=groupNativeArtifacts(versions.map(item=>item.latest))
  const limited=files.some(file=>file.delivery_status==='limited')
  const limitations=[...new Set(files.flatMap(file=>file.delivery_limitations||[]))]
  const singleDocument=versions.length===1&&groups.other.length===1&&['text/html','application/pdf'].includes(groups.other[0].media_type)
  const card=(file:NativeArtifact,label:string)=><button key={file.artifact_id} type="button" className="capstone-result-product" aria-label={`打开指令文件：${file.file_name}${label.startsWith('历史版本')?` · ${label}`:''}`} onClick={()=>onOpen(file)}><FileCheck2 aria-hidden="true"/><span><strong>{file.file_name}</strong><small><time dateTime={file.saved_at}>{nativeArtifactSavedTime(file)}</time></small><small>{label} · {Math.ceil(file.size_bytes/1024)} KB</small></span><span aria-hidden="true">↗</span></button>
  const cards=(items:NativeArtifact[],label:string)=><div className="capstone-result-products">{items.map(file=>{
    const history=versions.find(item=>item.latest===file)!.history
    return <div key={`${file.task_id}:${file.artifact_id}`}>
      {card(file,history.length?`${label} · 最新版`:label)}
      {history.length>0&&<details><summary>历史版本 · {history.length}</summary>{history.map((previous,index)=>card(previous,`历史版本 ${history.length-index}`))}</details>}
    </div>
  })}</div>
  return <div className="capstone-instruction-files">
    {limited&&<p role="status">有限交付 · 保留已知问题与未检查项</p>}
    {cards(groups.primary,'主要输出')}
    {limitations.length>0&&<details><summary>交付限制 · {limitations.length}</summary><ul>{limitations.map(text=><li key={text}>{text}</li>)}</ul></details>}
    {groups.support.length>0&&<details><summary>支撑材料 · {groups.support.length}</summary>{cards(groups.support,'支撑材料')}</details>}
    {groups.reproduction.length>0&&<details><summary>复算材料 · {groups.reproduction.length}</summary>{cards(groups.reproduction,'复算材料')}</details>}
    {singleDocument ? cards(groups.other,'生成文档') : groups.other.length>0&&<details><summary>过程文件 · {groups.other.length}</summary>{cards(groups.other,'过程文件')}</details>}
  </div>
}
