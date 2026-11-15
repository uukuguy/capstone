import {useEffect,useState} from 'react'
import type {ResourceRead,ResourceReadClient,ResourceReadPage} from './resourceReads'
/** Host receipts describe bytes returned, not understanding or Authority evidence. */
export default function ResourceReadSources({client,threadId,attemptId,revision}:{client:ResourceReadClient;threadId:string;attemptId:string;revision:number}){
 const [retry,setRetry]=useState(0),[page,setPage]=useState<ResourceReadPage>(),[error,setError]=useState(''),[loading,setLoading]=useState(true),[cursor,setCursor]=useState<string>()
 const [preview,setPreview]=useState<ResourceRead>(),[selected,setSelected]=useState<string>(),[previewError,setPreviewError]=useState('')
 useEffect(()=>{setCursor(undefined)},[threadId,attemptId,revision,retry])
 useEffect(()=>{
  const controller=new AbortController();setLoading(true);setError('');setPreview(undefined);setSelected(undefined)
  if(!cursor)setPage(undefined)
  void client.listResourceReads!(threadId,attemptId,cursor,controller.signal).then(value=>{
   if(controller.signal.aborted)return
   if(cursor&&value.next_cursor===cursor)throw new Error('来源游标未前进')
   setPage(previous=>({...value,items:cursor?[...(previous?.items??[]),...value.items]:value.items}))
  }).catch(cause=>{if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:'资源读取来源暂不可用')}).finally(()=>{if(!controller.signal.aborted)setLoading(false)})
  return()=>controller.abort()
 },[client,threadId,attemptId,revision,retry,cursor])
 useEffect(()=>{
  if(!selected||!client.readResourceRead)return
  const controller=new AbortController();setPreviewError('');setPreview(undefined)
  void client.readResourceRead(threadId,selected,attemptId,controller.signal).then(value=>{if(!controller.signal.aborted)setPreview(value)}).catch(()=>{if(!controller.signal.aborted)setPreviewError('预览读取失败，请重试。')})
  return()=>controller.abort()
 },[client,threadId,attemptId,selected,revision,retry])
 return <details className="thread-product-sources resource-read-sources"><summary>资源读取来源{page&&!error&&!loading?` · ${page.items.length}${page.next_cursor?'+':''}`:''}</summary>
  <p>按所选成果的生成执行列出。回执仅表示已返回的字节，不表示完整分析。</p>
  {loading&&<p role="status">正在读取来源…</p>}
  {error?<p role="alert">{error}<button type="button" onClick={()=>setRetry(n=>n+1)}>重试来源</button></p>:!loading&&!page?.items.length&&<p>此执行没有已确认的资源范围读取。</p>}
  <ul>{page?.items.map(item=><li key={item.read_id}><strong>{item.resource.file_name} · v{item.resource.version}</strong>
   <p>字节 {item.offset}–{item.offset+item.length-1}（从 0 开始） · 返回 {item.length} / {item.resource.size_bytes} 字节 · {item.length===item.resource.size_bytes?'此回执覆盖全部字节':'部分覆盖；此回执仅覆盖上述范围；其他范围请查看其他回执'}</p>
   <p>资源 SHA-256：<code>{item.resource.sha256}</code></p><p>片段 SHA-256：<code>{item.sha256}</code></p>
   {client.readResourceRead&&<button type="button" onClick={()=>{setSelected(undefined);setPreviewError('');setSelected(item.read_id)}}>查看有界预览</button>}
   {selected===item.read_id&&(previewError?<p role="alert">{previewError}<button type="button" onClick={()=>setRetry(n=>n+1)}>重试来源</button></p>:preview?<div><p>预览 {preview.preview.bytes_read} 字节{preview.preview.truncated?' · 预览已截断':''}</p>{preview.preview.status==='text'?<pre>{preview.preview.text}</pre>:<p>{preview.preview.status==='binary'?'二进制片段，无文本预览。':'片段含不完整或无效 UTF-8，无文本预览。'}</p>}</div>:<p role="status">正在读取预览…</p>)}
  </li>)}</ul>
  {page?.next_cursor&&<button type="button" disabled={loading} onClick={()=>setCursor(page.next_cursor!)}>更多读取回执</button>}
 </details>
}
