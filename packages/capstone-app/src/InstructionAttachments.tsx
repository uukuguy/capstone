import type {ThreadMessageLike} from '@assistant-ui/react'
import {useEffect,useState} from 'react'
import {FileText} from 'lucide-react'
import type {StoredResource} from './resourceUploads'
import {applicationCapacity} from './applicationCapacity'
import {NativeFileContent,nativePreviewMedia} from './NativeArtifactsWorkspace'

export type InstructionFile={resource_id:string;file_name?:string;size_bytes?:number;version?:number;sha256?:string}
export type InstructionFileReader=(file:InstructionFile,signal?:AbortSignal)=>Promise<Uint8Array>
export type InstructionFileSaver=(file:InstructionFile,signal?:AbortSignal)=>Promise<void>

/** Bind only resources named by this accepted instruction. No file bytes are read. */
export function bindInstructionAttachments(messages:ThreadMessageLike[],resources:StoredResource[]):ThreadMessageLike[]{
  const directory=new Map(resources.map(file=>[file.resource_id,file]))
  return messages.map(message=>{
    const custom=message.metadata?.custom
    if(message.role!=='user'||!Array.isArray(custom?.attachmentRefs)||!custom.attachmentRefs.length)return message
    const instructionFiles=custom.attachmentRefs.filter((ref):ref is string=>typeof ref==='string').map(ref=>{
      const file=directory.get(ref)
      return file?{resource_id:ref,file_name:file.file_name,size_bytes:file.size_bytes,version:file.version,sha256:file.sha256}:{resource_id:ref}
    })
    return {...message,metadata:{...message.metadata,custom:{...custom,instructionFiles}}}
  })
}

function InstructionFileItem({file,readFile,saveFile}:{file:InstructionFile;readFile?:InstructionFileReader;saveFile?:InstructionFileSaver}){
  const name=file.file_name||'附件信息暂不可用'
  const ready=!!readFile&&!!file.sha256&&file.size_bytes!==undefined&&file.size_bytes>0
  const overPreview=ready&&file.size_bytes!>applicationCapacity('preview_bytes')
  const media=nativePreviewMedia(file.file_name||'','application/octet-stream')
  const [open,setOpen]=useState(false)
  const [phase,setPhase]=useState<'idle'|'loading'|'ready'|'error'>('idle')
  const [url,setUrl]=useState<string>()
  const [text,setText]=useState<string>()
  const [textUnavailable,setTextUnavailable]=useState(false)
  const [error,setError]=useState('')
  useEffect(()=>()=>{if(url)URL.revokeObjectURL(url)},[url])
  async function materialize(){
    if(!readFile)throw new Error('附件暂时无法读取。')
    if(phase==='ready'&&url)return url
    setPhase('loading');setError('')
    const bytes=await readFile(file)
    const next=URL.createObjectURL(new Blob([new Uint8Array(bytes)],{type:media}))
    setUrl(current=>{if(current)URL.revokeObjectURL(current);return next})
    if(media.startsWith('text/')||media==='application/json'){
      try{setText(new TextDecoder('utf-8',{fatal:true}).decode(bytes));setTextUnavailable(false)}
      catch{setText(undefined);setTextUnavailable(true)}
    }else{setText(undefined);setTextUnavailable(false)}
    setPhase('ready')
    return next
  }
  async function preview(){
    if(!ready)return
    setOpen(true)
    if(overPreview){setError('');return}
    try{await materialize()}catch(cause){setPhase('error');setError(cause instanceof Error?cause.message:'附件暂时无法读取。')}
  }
  async function download(){
    if(!ready||!readFile)return
    setError('')
    try{
      if(file.size_bytes!>applicationCapacity('artifact_file_bytes')){
        if(!saveFile)throw new Error(`此文件超过浏览器内可校验读取的容量（${applicationCapacity('artifact_file_bytes')} 字节）。`)
        await saveFile(file)
        return
      }
      const href=await materialize()
      const link=document.createElement('a')
      link.href=href
      link.download=file.file_name||'附件'
      link.click()
    }catch(cause){setPhase(current=>current==='loading'?'error':current);setError(cause instanceof Error?cause.message:'附件暂时无法下载。')}
  }
  const size=file.size_bytes===undefined?undefined:file.size_bytes>=1024**3?`${(file.size_bytes/1024**3).toFixed(1)} GB`:file.size_bytes>=1024**2?`${(file.size_bytes/1024**2).toFixed(1)} MB`:`${Math.ceil(file.size_bytes/1024)} KB`
  return <li className={open?'is-open':undefined}>
    <FileText aria-hidden="true"/>
    <span><strong title={file.file_name}>{name}</strong>{size&&<small>{size}{file.version!==undefined?` · v${file.version}`:''}</small>}</span>
    {ready&&<span className="capstone-instruction-file-actions">
      <button type="button" aria-expanded={open} aria-label={`预览附件 ${name}`} onClick={()=>void preview()}>预览</button>
      <button type="button" aria-label={`下载附件 ${name}`} onClick={()=>void download()}>下载</button>
    </span>}
    {open&&<div className="capstone-instruction-file-preview">
      {phase==='loading'&&<p role="status">正在读取附件…</p>}
      {error&&<p role="alert">{error}</p>}
      {overPreview&&<NativeFileContent name={name} media={media} previewSize={file.size_bytes}/>}
      {!overPreview&&phase==='ready'&&<NativeFileContent name={name} media={media} url={url} text={text} textUnavailable={textUnavailable} previewSize={file.size_bytes}/>}
    </div>}
  </li>
}

export default function InstructionAttachments({files,readFile,saveFile}:{files:InstructionFile[];readFile?:InstructionFileReader;saveFile?:InstructionFileSaver}){
  if(!files.length)return null
  return <ul className="capstone-instruction-files" aria-label="指令附件">{files.map(file=><InstructionFileItem key={file.resource_id} file={file} readFile={readFile} saveFile={saveFile}/>)}</ul>
}
