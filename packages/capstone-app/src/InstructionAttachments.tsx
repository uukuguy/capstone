import type {ThreadMessageLike} from '@assistant-ui/react'
import {FileText} from 'lucide-react'
import type {StoredResource} from './resourceUploads'

export type InstructionFile={resource_id:string;file_name?:string;size_bytes?:number;version?:number}

/** Bind only resources named by this accepted instruction. No file bytes are read. */
export function bindInstructionAttachments(messages:ThreadMessageLike[],resources:StoredResource[]):ThreadMessageLike[]{
  const directory=new Map(resources.map(file=>[file.resource_id,file]))
  return messages.map(message=>{
    const custom=message.metadata?.custom
    if(message.role!=='user'||!Array.isArray(custom?.attachmentRefs)||!custom.attachmentRefs.length)return message
    const instructionFiles=custom.attachmentRefs.filter((ref):ref is string=>typeof ref==='string').map(ref=>{
      const file=directory.get(ref)
      return file?{resource_id:ref,file_name:file.file_name,size_bytes:file.size_bytes,version:file.version}:{resource_id:ref}
    })
    return {...message,metadata:{...message.metadata,custom:{...custom,instructionFiles}}}
  })
}

export default function InstructionAttachments({files}:{files:InstructionFile[]}){
  if(!files.length)return null
  const size=(bytes:number)=>bytes>=1024**3?`${(bytes/1024**3).toFixed(1)} GB`:bytes>=1024**2?`${(bytes/1024**2).toFixed(1)} MB`:`${Math.ceil(bytes/1024)} KB`
  return <ul className="capstone-instruction-files" aria-label="指令附件">{files.map(file=><li key={file.resource_id}>
    <FileText aria-hidden="true"/><span><strong title={file.file_name}>{file.file_name||'附件信息暂不可用'}</strong>{file.size_bytes!==undefined&&<small>{size(file.size_bytes)} · v{file.version}</small>}</span>
  </li>)}</ul>
}
