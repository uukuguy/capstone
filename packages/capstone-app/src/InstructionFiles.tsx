import {FileCheck2} from 'lucide-react'
import {groupNativeArtifacts,type NativeArtifact} from './nativeArtifacts'

/** Uses persisted purposes. A primary output is not automatically accepted delivery. */
export default function InstructionFiles({files,onOpen}:{files:NativeArtifact[];onOpen:(file:NativeArtifact)=>void}) {
  const groups=groupNativeArtifacts(files)
  const limited=files.some(file=>file.delivery_status==='limited')
  const limitations=[...new Set(files.flatMap(file=>file.delivery_limitations||[]))]
  const singleDocument=files.length===1&&groups.other.length===1&&['text/html','application/pdf'].includes(files[0].media_type)
  const cards=(items:NativeArtifact[],label:string)=><div className="capstone-result-products">{items.map(file=><button key={file.artifact_id} type="button" className="capstone-result-product" aria-label={`打开指令文件：${file.file_name}`} onClick={()=>onOpen(file)}><FileCheck2 aria-hidden="true"/><span><strong>{file.file_name}</strong><small>{label} · {Math.ceil(file.size_bytes/1024)} KB</small></span><span aria-hidden="true">↗</span></button>)}</div>
  return <div className="capstone-instruction-files">
    {limited&&<p role="status">有限交付 · 保留已知问题与未检查项</p>}
    {cards(groups.primary,'主要输出')}
    {limitations.length>0&&<details><summary>交付限制 · {limitations.length}</summary><ul>{limitations.map(text=><li key={text}>{text}</li>)}</ul></details>}
    {groups.support.length>0&&<details><summary>支撑材料 · {groups.support.length}</summary>{cards(groups.support,'支撑材料')}</details>}
    {groups.reproduction.length>0&&<details><summary>复算材料 · {groups.reproduction.length}</summary>{cards(groups.reproduction,'复算材料')}</details>}
    {singleDocument ? cards(groups.other,'生成文档') : groups.other.length>0&&<details><summary>过程文件 · {groups.other.length}</summary>{cards(groups.other,'过程文件')}</details>}
  </div>
}
