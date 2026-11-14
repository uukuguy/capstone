import {useEffect,useRef,useState} from 'react'
import {sha256Hex} from './browserDigest'
import type {BlockReader,BlockJob,BlockPage} from './productBlocks'
import type {LocalProductSelection,ProductRef} from './threadProducts'

export default function ProductParagraphPicker({source,bytes,read,onSelect}:{source:ProductRef;bytes:Uint8Array;read:BlockReader;onSelect:(selection:LocalProductSelection)=>void}) {
  const [job,setJob]=useState<BlockJob>(),[page,setPage]=useState<BlockPage>()
  const [texts,setTexts]=useState<string[]>([]),[offset,setOffset]=useState(0)
  const [busy,setBusy]=useState(false),[error,setError]=useState('')
  const active=useRef<AbortController|undefined>(undefined)
  useEffect(()=>()=>active.current?.abort(),[])
  async function load(next=0){
    active.current?.abort();const controller=new AbortController();active.current=controller
    setBusy(true);setError('');setPage(undefined)
    try{
      const result=await read(source,job?.job_id,next,controller.signal)
      const texts=[]
      if(result.page)for(const block of result.page.blocks){
        if(block.byte_end>bytes.length)throw new Error('段落范围超出成果内容')
        const data=bytes.slice(block.byte_start,block.byte_end)
        if(await sha256Hex(data)!==block.content_digest)throw new Error('段落内容校验失败')
        texts.push(new TextDecoder('utf-8',{fatal:true}).decode(data))
      }
      if(controller.signal.aborted)return
      setJob(result.job);setPage(result.page);setTexts(texts);setOffset(next)
      if(result.job.state==='failed')setError('段落准备失败，请使用整份成果引用。')
    }catch(cause){if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'段落暂不可用')}
    finally{if(!controller.signal.aborted)setBusy(false)}
  }
  return <details><summary>选择段落引用</summary>
    <p>引用固定版本中的段落；代码块、表格和列表暂不支持。</p>
    {!page&&<button type="button" disabled={busy||job?.state==='failed'} onClick={()=>void load(offset)}>{busy?'正在准备…':job?'刷新段落状态':'准备段落'}</button>}
    {job&&(job.state==='queued'||job.state==='running')&&<p role="status">段落正在准备，可稍后刷新状态。</p>}
    {error&&<p role="alert">{error}</p>}
    {page&&<><ol start={offset+1}>{page.blocks.map((block,index)=><li key={block.block_id}>
      <p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{texts[index]}</p>
      <button type="button" onClick={()=>onSelect({schema:'capstone-local-product-selection/1',parent_ref:source,index_ref:page.index_ref,block_id:block.block_id,content_digest:block.content_digest,purpose:'historical-context'})}>引用段落 {offset+index+1}</button>
    </li>)}</ol>{!page.blocks.length&&<p>此成果没有支持引用的段落。</p>}
    {offset>0&&<button type="button" disabled={busy} onClick={()=>void load(0)}>回到首页</button>}
    {page.next_offset!==null&&<button type="button" disabled={busy} onClick={()=>void load(page.next_offset!)}>下一页</button>}</>}
  </details>
}
