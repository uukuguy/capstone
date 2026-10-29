import {applicationCapacity,assertCapacity} from './applicationCapacity'
import {useEffect,useRef,useState} from 'react'
import {Paperclip, FileText, X} from 'lucide-react'
import {parseThreadMaterial,type ThreadMaterial} from './threadMaterials'
import './threadMaterialUpload.css'
import type {ResourceTransferOptions, StoredResource} from './resourceUploads'
import {readUploadResume,saveUploadResume,type UploadResume} from './resourceUploadResume'

/** A composer extension for real session materials. It never submits an instruction. */
export default function ThreadMaterialUpload({threadId,upload,onUploaded,disabled=false,onBusyChange,remainingBytes=applicationCapacity('inline_material_bytes'),remainingFiles=applicationCapacity('inline_material_count'),disabledReason,resourceUpload,cancelResource,attachments=[],onResourceUploaded,onRemoveAttachment}: {
  threadId:string;upload:(file:File,signal:AbortSignal)=>Promise<unknown>;onUploaded:(material:ThreadMaterial)=>void
  disabled?:boolean;onBusyChange?:(busy:boolean)=>void;remainingBytes?:number;remainingFiles?:number;disabledReason?:string
  resourceUpload?:(file:File,options:ResourceTransferOptions)=>Promise<unknown>
  cancelResource?:(id:string)=>Promise<unknown>
  attachments?:StoredResource[];onResourceUploaded?:()=>void;onRemoveAttachment?:(id:string)=>Promise<void>
}) {
  const input=useRef<HTMLInputElement>(null)
  const request=useRef<AbortController|undefined>(undefined)
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const [error,setError]=useState('')
  const [resume,setResume]=useState<UploadResume|undefined>(()=>readUploadResume(threadId))
  useEffect(()=>{setBusy(false);setMessage('');setError('');setResume(readUploadResume(threadId));return()=>{request.current?.abort();request.current=undefined}},[threadId])
  const [dragging,setDragging]=useState(false)
  const dragDepth=useRef(0)
  const uploadFiles=async(files:File[])=>{
    if(!files.length||disabled||busy||request.current&&!request.current.signal.aborted)return
      const controller=new AbortController()
      request.current=controller
      setError('');setMessage('');setBusy(true);onBusyChange?.(true)
      try{
        let available=remainingBytes
        let slots=remainingFiles
        let pendingResume=resume
        for(const file of files){
        if(resourceUpload){
          if(pendingResume&&(pendingResume.name!==file.name||pendingResume.size!==file.size||pendingResume.modified!==file.lastModified))throw new Error(`请重新选择 ${pendingResume.name} 以继续上传。`)
          let receipt=pendingResume||{requestId:crypto.randomUUID(),name:file.name,size:file.size,modified:file.lastModified}
          setResume(receipt);saveUploadResume(threadId,receipt)
          await resourceUpload(file,{signal:controller.signal,requestId:receipt.requestId,uploadId:receipt.uploadId,draft:true,
            onSession:id=>{receipt={...receipt,uploadId:id};setResume(receipt);saveUploadResume(threadId,receipt)},
            onProgress:(bytes,total)=>{if(!controller.signal.aborted)setMessage(bytes===total?'正在校验并保存…':`上传 ${Math.floor(bytes/total*100)}% · ${file.name}`)}})
          if(controller.signal.aborted)return
          saveUploadResume(threadId);setResume(undefined);pendingResume=undefined
          setMessage('');onResourceUploaded?.()
          continue
        }
        if(!/\.(txt|md|csv)$/i.test(file.name))throw new Error('当前支持 UTF-8 的 txt、md 和 csv 文件；暂不支持 PDF 或 OCR。')
        if(file.size<1)throw new Error('资料文件不能为空。')
        assertCapacity(file.size,'inline_material_bytes')
        if(slots<1)throw new Error(`超过应用容量 inline_material_count：上限 ${applicationCapacity('inline_material_count')} 份。`)
        if(file.size>available)throw new Error(`超过应用容量 inline_material_bytes：可用 ${available} 字节，请先移除部分资料。`)
        try{new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer())}catch{throw new Error('请上传 UTF-8 编码的文本资料。')}
        if(controller.signal.aborted)return
        const material=parseThreadMaterial(await upload(file,controller.signal),threadId)
        if(controller.signal.aborted)return
        available-=file.size
        slots--
        onUploaded(material)
        setMessage(`${material.file_name} 已上传。`)
        }
      }catch(cause){if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'资料上传失败，请重试。')}
      finally{if(request.current===controller){request.current=undefined;setBusy(false);onBusyChange?.(false)}}
  }
  useEffect(()=>{
    const zone=input.current?.closest('.workspace-shell')||input.current?.parentElement
    if(!zone)return
    const isFile=(event:DragEvent)=>Array.from(event.dataTransfer?.types||[]).includes('Files')
    const enter=(event:Event)=>{const drag=event as DragEvent;if(!isFile(drag))return;drag.preventDefault();dragDepth.current++;setDragging(true)}
    const over=(event:Event)=>{const drag=event as DragEvent;if(!isFile(drag))return;drag.preventDefault();if(drag.dataTransfer)drag.dataTransfer.dropEffect=disabled||busy?'none':'copy'}
    const leave=(event:Event)=>{const drag=event as DragEvent;if(!isFile(drag))return;dragDepth.current=Math.max(0,dragDepth.current-1);if(!dragDepth.current)setDragging(false)}
    const drop=(event:Event)=>{
      const drag=event as DragEvent;if(!isFile(drag))return
      drag.preventDefault();drag.stopPropagation();dragDepth.current=0;setDragging(false)
      if(disabled||busy){setError('当前操作尚未完成，请稍后再上传。');return}
      const files=Array.from(drag.dataTransfer?.files||[])
      if(!files.length){setError('请拖入文件，暂不支持文件夹。');return}
      void uploadFiles(files)
    }
    const reset=()=>{dragDepth.current=0;setDragging(false)}
    zone.addEventListener('dragenter',enter);zone.addEventListener('dragover',over);zone.addEventListener('dragleave',leave);zone.addEventListener('drop',drop)
    window.addEventListener('dragend',reset);window.addEventListener('blur',reset)
    return()=>{zone.removeEventListener('dragenter',enter);zone.removeEventListener('dragover',over);zone.removeEventListener('dragleave',leave);zone.removeEventListener('drop',drop);window.removeEventListener('dragend',reset);window.removeEventListener('blur',reset)}
  })
  return <span className="thread-material-upload">
    {!!attachments.length&&<span className="thread-draft-attachments" aria-label="待发送附件">{attachments.map(file=><span className="thread-draft-attachment" key={file.resource_id}>
      <FileText aria-hidden="true"/><span title={file.file_name}><strong>{file.file_name}</strong><small>{file.size_bytes<1024*1024?`${Math.ceil(file.size_bytes/1024)} KB`:`${(file.size_bytes/1024/1024).toFixed(1)} MB`} · 待发送</small></span>
      <button type="button" disabled={disabled||busy} aria-label={`移除附件 ${file.file_name}`} title="移除附件" onClick={async()=>{setError('');setBusy(true);onBusyChange?.(true);try{await onRemoveAttachment?.(file.resource_id)}catch(cause){setError(cause instanceof Error?cause.message:'移除失败，请重试。')}finally{setBusy(false);onBusyChange?.(false)}}}><X aria-hidden="true"/></button>
    </span>)}</span>}
    {dragging&&<span className="thread-material-drop-hint" role="status">{disabled||busy?'当前操作完成后可上传':'松开文件，上传到当前会话'}</span>}
    <input ref={input} hidden type="file" multiple aria-label="上传资料文件" accept={resourceUpload?undefined:'.txt,.md,.csv,text/plain,text/markdown,text/csv'} disabled={disabled||busy} onChange={event=>{const files=Array.from(event.target.files||[]);event.target.value='';void uploadFiles(files)}}/>
    <button type="button" className="thread-material-upload-button" aria-label="上传资料" title={disabledReason||(resourceUpload?'上传资料；中断后重新选择原文件可继续':`上传 UTF-8 的 txt、md 或 csv，单文件及所选总量不超过 ${Math.ceil(applicationCapacity('inline_material_bytes')/1024)} KiB`)} disabled={disabled||busy} onClick={()=>input.current?.click()}><Paperclip aria-hidden="true"/>{busy?'上传中…':resume?'继续上传':'上传资料'}</button>
    {busy&&resourceUpload&&<button type="button" className="thread-material-upload-button" onClick={()=>{request.current?.abort();setMessage('上传已暂停；重新选择原文件可继续。')}}>暂停上传</button>}
    {!busy&&resume&&cancelResource&&<button type="button" className="thread-material-upload-button" disabled={disabled} onClick={async()=>{
      setBusy(true);onBusyChange?.(true);setError('')
      try{if(resume.uploadId)await cancelResource(resume.uploadId);saveUploadResume(threadId);setResume(undefined);setMessage('上传已取消。')}
      catch(cause){setError(cause instanceof Error?cause.message:'取消失败，请重试。')}
      finally{setBusy(false);onBusyChange?.(false)}
    }}>取消上传</button>}
    {message&&<span role="status">{message}</span>}{error&&<span role="alert">{error}</span>}
  </span>
}
