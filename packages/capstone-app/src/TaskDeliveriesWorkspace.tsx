import {applicationCapacity,exceedsCapacity} from './applicationCapacity'
import {useEffect,useRef,useState} from 'react'
import {useSessionViewState,useSessionObjectUrls,sessionObjectUrl} from './workspaceSessionCache'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type {CapstoneThreadClient} from './threadClient'
import type {ProcessProduct} from './processProducts'
import {commandKey} from './commandKey'
import './taskDeliveries.css'
import type {NativeArtifact} from './nativeArtifacts'

type Delivery={artifact_id:string;revision:number;title:string;work_id:string|null;request:{request_id:string;scope:string};supporting_process_ids:string[];media_type?:string;file_name?:string;format?:string;byte_size?:number;content_digest?:string;generation_status?:string}
export function parseDeliveries(value:unknown,threadId:string):{items:Delivery[];more:boolean;before:number|undefined} {
  const page=value as Record<string,unknown>
  if(!page||page.schema!=='capstone-deliveries/1'||page.thread_id!==threadId||!Array.isArray(page.deliveries)||exceedsCapacity(page.deliveries.length,'product_page_items')||typeof page.has_more!=='boolean'||!(page.next_before_event_seq===null&&!page.has_more||Number.isSafeInteger(page.next_before_event_seq)&&(page.next_before_event_seq as number)>=1))throw new Error('交付目录无效')
  const items=page.deliveries.map(item=>{
    if(!item||item.scope!=='task'||item.thread_id!==threadId||typeof item.artifact_id!=='string'||!/^delivery_[a-f0-9]{32}$/.test(item.artifact_id)||!Number.isSafeInteger(item.revision)||item.revision<1||typeof item.title!=='string'||exceedsCapacity(item.title.length,'ui_delivery_title_chars')||!item.request||typeof item.request.request_id!=='string'||typeof item.request.scope!=='string'||!Array.isArray(item.supporting_process_ids)||item.supporting_process_ids.some((ref:unknown)=>typeof ref!=='string'))throw new Error('交付来源无效')
    if(item.format==='native-file'&&(!Number.isSafeInteger(item.byte_size)||item.byte_size<0||exceedsCapacity(item.byte_size,'delivery_file_bytes')||typeof item.content_digest!=='string'||!/^[a-f0-9]{64}$/.test(item.content_digest)||typeof item.file_name!=='string'||/[\\/\u0000-\u001f]/.test(item.file_name)||typeof item.media_type!=='string'))throw new Error('交付文件信息无效')
    return item as Delivery
  })
  return {items,more:page.has_more,before:page.next_before_event_seq===null?undefined:page.next_before_event_seq as number}
}

export default function TaskDeliveriesWorkspace({client,threadId,revision,onPublished,requestedArtifact}:{client:CapstoneThreadClient;threadId:string;revision:number;onPublished?:()=>void;requestedArtifact?:NativeArtifact}) {
  const [items,setItems]=useState<Delivery[]>([]),[sources,setSources]=useState<ProcessProduct[]>([])
  const [selected,setSelected]=useState<Delivery>(),[content,setContent]=useState('')
  const [savedSelection,setSavedSelection]=useSessionViewState<{id:string;revision:number}|undefined>('deliveries.selection',undefined)
  const sessionUrls=useSessionObjectUrls(),loadedContent=useRef<string|undefined>(undefined)
  const [fileBytes,setFileBytes]=useState<Uint8Array>(),[fileUrl,setFileUrl]=useState(''),[adopting,setAdopting]=useState<NativeArtifact>()
  const [editing,setEditing]=useState(false),[title,setTitle]=useState(''),[scope,setScope]=useState('')
  const [refs,setRefs]=useState<string[]>([]),[update,setUpdate]=useState<Delivery>()
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[reload,setReload]=useState(0)
  const [sourceCursor,setSourceCursor]=useState<number>(),[sourceMore,setSourceMore]=useState(false)
  const [deliveryCursor,setDeliveryCursor]=useState<number>(),[deliveryMore,setDeliveryMore]=useState(false)
  const pending=useRef<Record<string,unknown> | undefined>(undefined)
  useEffect(()=>{if(!requestedArtifact||requestedArtifact.thread_id!==threadId)return
    pending.current=undefined;setAdopting(requestedArtifact);setUpdate(undefined);setTitle(requestedArtifact.file_name);setScope('');setRefs([`process_${requestedArtifact.attempt_id}`]);setEditing(true);setError('')
  },[requestedArtifact,threadId])
  async function readSources(signal:AbortSignal){
    let page=await client.processProducts(threadId,undefined,signal)
    for(let count=0;!page.products.length&&page.hasMore&&count<applicationCapacity('artifact_initial_pages');count++)page=await client.processProducts(threadId,page.nextBefore,signal)
    return page
  }
  useEffect(()=>{const abort=new AbortController();setError('')
    void Promise.all([client.deliveries(threadId,undefined,abort.signal),readSources(abort.signal)]).then(([raw,page])=>{
      if(abort.signal.aborted)return
      const list=parseDeliveries(raw,threadId);setItems(list.items);setDeliveryCursor(list.before);setDeliveryMore(list.more)
      setSources(page.products);setSourceCursor(page.nextBefore);setSourceMore(page.hasMore)
    }).catch(()=>{if(!abort.signal.aborted)setError('目录暂时无法读取，请重试')})
    return ()=>abort.abort()
  },[client,threadId,revision,reload])
  useEffect(()=>{
    if(selected){setSavedSelection({id:selected.artifact_id,revision:selected.revision});return}
    const found=items.find(item=>item.artifact_id===savedSelection?.id&&item.revision===savedSelection.revision)
    if(found)setSelected(found)
  },[selected,items,savedSelection?.id,savedSelection?.revision])
  useEffect(()=>{
    const selectionKey=selected?`${selected.artifact_id}:${selected.revision}:${selected.content_digest}`:undefined
    if(sessionUrls&&selectionKey&&loadedContent.current===selectionKey)return
    setContent('');setFileBytes(undefined);setFileUrl('');if(!selected)return;const abort=new AbortController();let url=''
    const read=client.supportsDeliveryFiles&&selected.byte_size!==undefined&&selected.content_digest
      ?client.deliveryFile(threadId,selected.artifact_id,selected.revision,selected.byte_size,selected.content_digest,abort.signal)
      :client.deliveryContent(threadId,selected.artifact_id,selected.revision,abort.signal).then(text=>new TextEncoder().encode(text))
    void read.then(bytes=>{if(abort.signal.aborted)return;loadedContent.current=selectionKey;setFileBytes(bytes)
      if(bytes.byteLength>applicationCapacity('preview_bytes'))return
      const media=selected.media_type?.split(';')[0]||'text/markdown'
      if(media.startsWith('text/')||media==='application/json')setContent(new TextDecoder().decode(bytes))
      else if(['image/png','image/jpeg','application/pdf'].includes(media)){url=sessionObjectUrl(sessionUrls,'delivery',selectionKey!,bytes,media);setFileUrl(url)}
    }).catch(()=>{if(!abort.signal.aborted)setError('文件读取失败，可重新选择版本重试')})
    return ()=>{abort.abort();if(url&&!sessionUrls)URL.revokeObjectURL(url)}
  },[client,threadId,selected])
  async function publish(){
    if(busy)return
    const trigger=adopting?{attemptId:adopting.attempt_id,workId:adopting.work_id}:sources.find(source=>refs.includes(source.productId)&&(!update||source.workId===update.work_id))
    if(!title.trim()||!scope.trim()||!trigger){setError('请填写名称与范围，并选择同一任务中的支撑指令');return}
    setBusy(true);setError('')
    const request=pending.current || {schema:'capstone-delivery-request/1',command_id:commandKey(),idempotency_key:commandKey(),request_id:update?.request.request_id||commandKey(),expected_revision:update?.revision||0,work_id:update?update.work_id:trigger.workId,trigger_attempt_id:trigger.attemptId,title:title.trim(),scope:scope.trim(),format:adopting?'native-file':'markdown',supporting_process_ids:refs,...(adopting?{source_artifact:{attempt_id:adopting.attempt_id,artifact_id:adopting.artifact_id}}:{})}
    pending.current=request
    try {
      const raw=await client.publishDelivery(threadId,request) as {status?:string;target?:{delivery?:Delivery};rejection_code?:string}
      if(raw.status!=='accepted'||!raw.target?.delivery){pending.current=undefined;throw new Error(raw.rejection_code==='revision_conflict'?'已有新版本，请刷新后再修订':'交付要求未接纳，请检查范围与来源')}
      const admitted=parseDeliveries({schema:'capstone-deliveries/1',thread_id:threadId,deliveries:[raw.target.delivery],has_more:false,next_before_event_seq:1},threadId).items[0]
      setSelected(admitted);setEditing(false);pending.current=undefined;setReload(value=>value+1);onPublished?.();window.dispatchEvent(new Event('capstone-session-renamed'))
    } catch(cause){setError(cause instanceof Error?cause.message:'交付未确认，重试会使用同一请求')}
    finally{setBusy(false)}
  }
  function begin(value?:Delivery){pending.current=undefined;setAdopting(undefined);setUpdate(value);setTitle(value?.title||'');setScope(value?.request.scope||'');setRefs(value?.supporting_process_ids||[]);setEditing(true);setError('')}
  return <section className="task-deliveries" aria-label="任务交付">
    <header><h3>任务交付</h3><button onClick={()=>begin()} disabled={busy}>生成交付材料</button></header>
    <p className="task-deliveries-note">可采用指令生成的已保存文件，或将选定过程与结果整理为 Markdown。交付可继续修订，会话仍可继续。</p>
    {error&&<p role="alert">{error}<button disabled={busy} onClick={()=>setReload(value=>value+1)}>刷新目录</button></p>}
    {editing&&<form onSubmit={event=>{event.preventDefault();void publish()}}>
      {adopting&&<><p>采用已保存文件：{adopting.file_name}。{adopting.source_status!=='completed'?'来源执行未完成，交付将保留该状态。':''}</p><label>交付版本<select disabled={busy} value={update?.request.request_id||''} onChange={event=>{const value=items.find(item=>item.request.request_id===event.target.value);setUpdate(value);if(value){setTitle(value.title);setScope(value.request.scope)}}}><option value="">创建新的任务交付</option>{items.filter((item,index)=>item.work_id===adopting.work_id&&items.findIndex(other=>other.request.request_id===item.request.request_id)===index).map(item=><option key={item.request.request_id} value={item.request.request_id}>修订：{item.title} · v{item.revision}</option>)}</select></label></>}
      <label>交付名称<input maxLength={applicationCapacity('ui_delivery_title_chars')} value={title} disabled={busy||Boolean(pending.current)} onChange={event=>setTitle(event.target.value)}/></label>
      <label>范围与用途<textarea maxLength={applicationCapacity('ui_delivery_scope_chars')} value={scope} disabled={busy||Boolean(pending.current)} onChange={event=>setScope(event.target.value)}/></label>
      {!adopting&&<fieldset disabled={busy||Boolean(pending.current)}><legend>支撑过程（最多 {applicationCapacity('ui_delivery_support_count')} 条）</legend>{sources.map(source=><label key={source.productId} className="delivery-source"><input type="checkbox" disabled={!refs.includes(source.productId)&&refs.length>=applicationCapacity('ui_delivery_support_count')} checked={refs.includes(source.productId)} onChange={event=>setRefs(old=>event.target.checked?(old.length<applicationCapacity('ui_delivery_support_count')?[...old,source.productId]:old):old.filter(ref=>ref!==source.productId))}/><span>{source.instruction}<small>{source.status==='completed'?'已完成':'未完成记录'} · {source.modelContext?.modelId||'通用任务'}</small></span></label>)}</fieldset>}
      {sourceMore&&<button type="button" disabled={busy} onClick={()=>void client.processProducts(threadId,sourceCursor).then(page=>{setSources(old=>[...old,...page.products.filter(item=>!old.some(value=>value.productId===item.productId))]);setSourceCursor(page.nextBefore);setSourceMore(page.hasMore)}).catch(()=>setError('更早记录读取失败'))}>读取更早的过程</button>}
      <div className="delivery-actions"><button type="submit" disabled={busy||!refs.length}>{busy?'正在保存…':pending.current?'重试同一交付请求':update?'生成新版本':adopting?'确认采用文件':'生成 Markdown'}</button><button type="button" disabled={busy} onClick={()=>{setEditing(false);pending.current=undefined}}>取消</button></div>
    </form>}
    {!items.length&&!editing&&<p>尚无任务级交付。指令结果仍在“过程制品”中。</p>}
    {items.length>0&&<label className="delivery-version">交付与版本<select value={selected?`${selected.artifact_id}:${selected.revision}`:''} onChange={event=>setSelected(items.find(item=>`${item.artifact_id}:${item.revision}`===event.target.value))}><option value="">选择交付版本</option>{items.map(item=><option key={`${item.artifact_id}:${item.revision}`} value={`${item.artifact_id}:${item.revision}`}>{item.title} · v{item.revision}</option>)}</select></label>}
    {deliveryMore&&<button onClick={()=>void client.deliveries(threadId,deliveryCursor).then(raw=>{const page=parseDeliveries(raw,threadId);setItems(old=>[...old,...page.items]);setDeliveryCursor(page.before);setDeliveryMore(page.more)}).catch(()=>setError('历史版本暂时无法读取'))}>更早的交付版本</button>}
    {selected&&<><div className="delivery-actions"><button disabled={!fileBytes} onClick={()=>{if(!fileBytes)return;const url=URL.createObjectURL(new Blob([new Uint8Array(fileBytes).buffer],{type:selected.media_type||'text/markdown'}));const link=document.createElement('a');link.href=url;link.download=selected.file_name||`${selected.title.replace(/[\\/:*?"<>|]/g,'_')}-v${selected.revision}.md`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}}>下载文件</button>{selected.format!=='native-file'&&<button onClick={()=>begin(selected)}>修订此交付</button>}</div>{selected.format==='native-file'&&<p className="task-deliveries-note">需要修订时，继续发出指令，再将新生成的文件采用为此交付的新版本。</p>}<article>{!fileBytes?'正在读取文件…':fileBytes.byteLength>applicationCapacity('preview_bytes')?`此文件超过内置预览容量（${applicationCapacity('preview_bytes')} 字节），可下载完整文件。`:fileUrl?(selected.media_type==='application/pdf'?<iframe title={selected.title} src={fileUrl} sandbox="allow-same-origin"/>:<img src={fileUrl} alt={selected.title}/>):content?(selected.media_type?.startsWith('text/markdown')||!selected.media_type?<ReactMarkdown remarkPlugins={[remarkGfm]} disallowedElements={['img']} skipHtml>{content}</ReactMarkdown>:<pre>{content}</pre>):'文件已保存，可下载查看。'}</article></>}
  </section>
}
