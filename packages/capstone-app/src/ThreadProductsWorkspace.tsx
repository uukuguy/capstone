import {applicationCapacity,observeCapacity,rethrowDebugCapacity,CapacityError} from './applicationCapacity'
import {useEffect,useRef,useState,type ReactNode} from 'react'
import {ArrowDownToLine,ArrowUpRight,FileCheck,LocateFixed,ListTree} from 'lucide-react'
import {ResultProjectionCard} from './CapstoneAssistantThread'
import {NativeFileContent,nativePreviewMedia} from './NativeArtifactsWorkspace'
import {parseNativeArtifact,type NativeArtifact} from './nativeArtifacts'
import {productRefKey,type ProductEntry,type ProductIndex,type ProductQuery,type ProductRef,type ProductResolution} from './threadProducts'
import './threadProducts.css'
import type {ResultProjection} from './threadProtocol'
import {useSessionViewState,useSessionViewRef,useSessionObjectUrls,sessionObjectUrl} from './workspaceSessionCache'

type ProductClient={productIndex:(threadId:string,query?:ProductQuery,signal?:AbortSignal)=>Promise<ProductIndex>;resolveProduct:(ref:ProductRef,signal?:AbortSignal)=>Promise<ProductResolution>}
export type ProductRequest={ref?:ProductRef;origin?:ProductRef['origin'];attemptId?:string;artifactId?:string;resultId?:string;workId?:string|null;nonce?:number}
/** Only host-bound primary files from the exact completed instruction may open automatically. */
function primaryProduct(items:ProductEntry[],threadId:string,workId:string|null|undefined,attemptId?:string){
  const mediaOrder=['text/html','application/pdf','text/markdown','text/plain','image/svg+xml','text/csv','application/json']
  return items.filter(item=>item.ref.thread_id===threadId&&item.ref.work_id===workId&&item.ref.attempt_id===attemptId
    &&item.ref.origin==='native_file'&&item.source.presentation_role==='primary')
    .sort((a,b)=>{
      const rank=(item:ProductEntry)=>{const type=nativePreviewMedia(typeof item.source.file_name==='string'?item.source.file_name:item.title,item.media_type);const at=mediaOrder.indexOf(type);return at<0?mediaOrder.length:at}
      return rank(a)-rank(b)||productRefKey(a.ref).localeCompare(productRefKey(b.ref))
    })[0]
}
const statuses:Record<string,string>={completed:'已完成',partial:'部分结果',failed:'未完成',cancelled:'已取消',interrupted:'已中断',blocked:'未执行'}
export const productSelectionReason=(reason:string|null)=>reason==='record_only'?'此项是执行记录，没有可引用的文件或分析结果。':reason==='input_capacity'?'此项超过本轮引用容量。':reason==='product_context_unsupported'?'当前执行链尚不支持此成果引用。':reason==='unsupported_media'?'当前执行链尚不能读取此文件格式。':'此项暂不可引用。'
const productStatus=(entry:ProductEntry)=>entry.source.delivery_status==='limited'?'有限交付 · 含未解决项':statuses[entry.source_status]||'状态未知'
function matches(entry:ProductEntry,request:ProductRequest){return request.ref?productRefKey(entry.ref)===productRefKey(request.ref)
  :entry.ref.origin===request.origin&&entry.ref.attempt_id===request.attemptId&&(!request.artifactId||entry.source.artifact_id===request.artifactId)&&(!request.resultId||entry.source.result_id===request.resultId)}

/** Read-only navigation over the host index. Viewing does not change Work or model context. */
export default function ThreadProductsWorkspace({client,threadId,workId,revision,requested,primaryAttemptId,onPrimaryReady,onIndexLoaded,onReference,onAdopt,onLocate,onInspect,onBrowse,onFocusElement,fallback}:{
  client:ProductClient;threadId:string;workId?:string|null;revision:number;requested?:ProductRequest
  primaryAttemptId?:string;onPrimaryReady?:(entry:ProductEntry)=>void
  onIndexLoaded?:(entries:readonly ProductEntry[])=>void
  onReference?:(entry:ProductEntry,excerpt?:{max_bytes:number})=>void;onAdopt?:(artifact:NativeArtifact)=>void;onLocate?:(attemptId:string)=>void;onInspect?:(attemptId:string)=>void
  fallback?:ReactNode
  onBrowse?:()=>void
  onFocusElement?:(projection:ResultProjection,elementId:string)=>boolean|void
}) {
  const [scope,setScope]=useSessionViewState('products.scope','current')
  const [directory,setDirectory]=useState<{threadId:string;items:ProductEntry[];more:boolean;cursor:string|null}>({threadId,items:[],more:false,cursor:null})
  const [fatalError,setFatalError]=useState<CapacityError>()
  const [selection,setSelection]=useSessionViewState<ProductRef|undefined>('products.selection',undefined)
  const [resolved,setResolved]=useState<ProductResolution>()
  const [loading,setLoading]=useState(false),[error,setError]=useState(''),[detailError,setDetailError]=useState(''),[retry,setRetry]=useState(0)
  const [fileUrl,setFileUrl]=useState<{key:string;url:string}>()
  const request=useRef<AbortController|undefined>(undefined),generation=useRef(0)
  const directoryElement=useRef<HTMLDetailsElement>(null)
  const requestedKey=JSON.stringify(requested||null)
  const consumedRequest=useRef('')
  const userSelected=useSessionViewRef('products.user-selected',false)
  const sessionUrls=useSessionObjectUrls()
  const primaryNotified=useRef(new Set<string>())
  const requestPending=!!requested&&consumedRequest.current!==requestedKey
  const current=directory.threadId===threadId?directory:undefined
  const view=!requestPending&&resolved?.entry.ref.thread_id===threadId&&selection&&productRefKey(resolved.entry.ref)===productRefKey(selection)?resolved:undefined
  const viewKey=view?productRefKey(view.entry.ref):''
  const url=fileUrl?.key===viewKey?fileUrl.url:''
  const fileName=view?(typeof view.entry.source.file_name==='string'?view.entry.source.file_name:view.entry.title):''
  const previewMedia=nativePreviewMedia(fileName,view?.entry.media_type)
  async function load(older=false){
    if(fatalError)return
    request.current?.abort();const controller=new AbortController();request.current=controller
    const token=++generation.current
    if(scope==='current'&&workId===undefined&&!requested){setDirectory({threadId,items:[],more:false,cursor:null});setLoading(false);return}
    setLoading(true);setError('')
    const query:ProductQuery=scope==='history'?{}:{workId}
    if(older&&current?.cursor)query.cursor=current.cursor
    try{
      let page=await client.productIndex(threadId,query,controller.signal)
      const loaded=[...page.products]
      const seekPrimary=scope==='current'&&!!primaryAttemptId&&!!onPrimaryReady&&!requested&&!userSelected.current
      const foundDocument=()=>{const item=primaryProduct(loaded,threadId,workId,primaryAttemptId);return !!item&&['text/html','application/pdf','text/markdown'].includes(nativePreviewMedia(typeof item.source.file_name==='string'?item.source.file_name:item.title,item.media_type))}
      let scanned=1
      for(let scan=1;((requested&&!requested.ref&&!loaded.some(item=>matches(item,requested)))||(seekPrimary&&!foundDocument()))&&page.hasMore&&scan<applicationCapacity('artifact_initial_pages');scan++){
        if(controller.signal.aborted||token!==generation.current)return
        const cursor=page.nextCursor
        page=await client.productIndex(threadId,{...query,cursor:cursor||undefined},controller.signal)
        if(page.hasMore&&page.nextCursor===cursor)throw new Error('目录游标未前进，请重试。')
        loaded.push(...page.products);scanned++
      }
      if(page.hasMore&&((requested&&!requested.ref&&!loaded.some(item=>matches(item,requested)))||(seekPrimary&&!foundDocument())))observeCapacity(scanned+1,'artifact_initial_pages','product.initial-scan')
      if(controller.signal.aborted||token!==generation.current)return
      if(query.cursor&&page.hasMore&&page.nextCursor===query.cursor)throw new Error('目录游标未前进，请重试。')
      const items=older?[...(current?.items||[]),...loaded]:loaded
      const unique=[...new Map(items.filter(item=>item.ref.thread_id===threadId).map(item=>[productRefKey(item.ref),item])).values()]
      setDirectory({threadId,items:unique,more:page.hasMore,cursor:page.nextCursor})
      onIndexLoaded?.(unique)
      if(requested&&consumedRequest.current!==requestedKey){
        const found=unique.find(item=>matches(item,requested))
        if(found){consumedRequest.current=requestedKey;userSelected.current=true;setSelection(found.ref)}
      }else if(!requested){
        const primary=primaryAttemptId?primaryProduct(unique,threadId,workId,primaryAttemptId):undefined
        const featured=primary||unique.find(item=>item.ref.scope==='task')||unique.find(item=>item.source.presentation_role==='primary')
        if(featured)setSelection(previous=>primary&&seekPrimary&&!userSelected.current?primary.ref:previous?.thread_id===threadId?previous:featured.ref)
        if(primary&&seekPrimary&&!userSelected.current&&!primaryNotified.current.has(primaryAttemptId!)){
          primaryNotified.current.add(primaryAttemptId!);onPrimaryReady?.(primary)
        }
      }
    }catch(cause){if(cause instanceof CapacityError&&cause.fatal){setFatalError(cause);return}rethrowDebugCapacity(cause);if(!controller.signal.aborted&&token===generation.current)setError(cause instanceof Error?cause.message:'成果目录暂不可用。')}
    finally{if(!controller.signal.aborted&&token===generation.current)setLoading(false)}
  }
  useEffect(()=>{void load();return()=>{generation.current++;request.current?.abort()}},[client,threadId,workId,scope,revision,retry,requestedKey,primaryAttemptId])
  useEffect(()=>{if(requested?.ref?.thread_id===threadId){consumedRequest.current=requestedKey;userSelected.current=true;setSelection(requested.ref)}},[requestedKey,threadId])
  useEffect(()=>{if(requested?.workId!==undefined&&requested.workId!==workId)setScope('history')},[requestedKey,workId])
  const selectedKey=selection?.thread_id===threadId?productRefKey(selection):''
  useEffect(()=>{
    if(!selection||selection.thread_id!==threadId)return
    if(sessionUrls&&view&&retry===0)return
    const controller=new AbortController();setDetailError('')
    void client.resolveProduct(selection,controller.signal).then(value=>{if(value.bytes)observeCapacity(value.bytes.byteLength,'preview_bytes','product.preview');if(!controller.signal.aborted)setResolved(value)}).catch(cause=>{if(cause instanceof CapacityError&&cause.fatal){setFatalError(cause);return}rethrowDebugCapacity(cause);if(!controller.signal.aborted)setDetailError(cause instanceof Error?cause.message:'成果内容暂不可用。')})
    return()=>controller.abort()
  },[client,threadId,selectedKey,retry])
  useEffect(()=>{if(!view?.bytes)return
    const url=sessionObjectUrl(sessionUrls,'product',viewKey,view.bytes,previewMedia);setFileUrl(previous=>previous?.key===viewKey&&previous.url===url?previous:{key:viewKey,url})
    return()=>{if(!sessionUrls)URL.revokeObjectURL(url)}
  },[view])
  let text:string|undefined,textUnavailable=false
  const groups=[
    {label:'任务交付',items:current?.items.filter(item=>item.ref.scope==='task')||[],collapsed:false},
    {label:'本轮主要成果',items:current?.items.filter(item=>item.ref.scope==='instruction'&&item.source.presentation_role==='primary')||[],collapsed:false},
    {label:'支撑图表与数据',items:current?.items.filter(item=>item.ref.scope==='instruction'&&item.source.presentation_role==='support')||[],collapsed:true},
    {label:'过程产物与记录',items:current?.items.filter(item=>item.ref.scope==='instruction'&&!['primary','support'].includes(String(item.source.presentation_role)))||[],collapsed:true},
  ]
  if(view?.bytes)observeCapacity(view.bytes.byteLength,'preview_bytes','product.preview')
  if(view?.bytes&&view.bytes.byteLength<=applicationCapacity('preview_bytes')&&(previewMedia.startsWith('text/')||previewMedia==='application/json')){try{text=new TextDecoder('utf-8',{fatal:true}).decode(view.bytes)}catch{textUnavailable=true}}
  if(fatalError)return <p role="alert">{fatalError.message}</p>
  return <section className="thread-products-workspace" aria-label="成果目录">
    <details ref={directoryElement} className="thread-products-directory" open={!view||undefined} onKeyDown={event=>{if(event.key==='Escape'&&event.currentTarget.open){event.stopPropagation();event.currentTarget.open=false;event.currentTarget.querySelector('summary')?.focus()}}}><summary title="浏览成果" aria-label="浏览成果"><ListTree aria-hidden="true"/><span>浏览成果{current?.items.length?` · ${current.items.length}`:''}</span></summary>
      <div className="thread-products-directory-body"><label>成果范围<select aria-label="成果范围" value={scope} onChange={event=>setScope(event.target.value)}><option value="current">当前工作</option><option value="history">会话历史</option></select></label>
      {!loading&&!current?.items.length&&!error&&<p>{scope==='current'?'当前工作暂无成果，可按需浏览会话历史。':'此段暂无成果。'}</p>}
      {groups.filter(group=>group.items.length).map(group=>{
        const list=<ul>{group.items.map(item=><li key={productRefKey(item.ref)}><button type="button" aria-label={`查看：${item.title}`} aria-pressed={selection&&productRefKey(item.ref)===selectedKey} onClick={()=>{userSelected.current=true;onBrowse?.();setSelection(item.ref);if(directoryElement.current)directoryElement.current.open=false}}><span>{item.title}</span><small>{item.ref.revision?`v${item.ref.revision} · `:''}{productStatus(item)}{item.ref.origin==='process_record'?' · 执行记录':''}</small></button></li>)}</ul>
        return group.collapsed?<details className="thread-product-secondary" key={group.label}><summary>{group.label} · {group.items.length}</summary>{list}</details>:<div key={group.label}><h4>{group.label}</h4>{list}</div>
      })}
      {loading&&<p role="status">正在读取成果目录…</p>}{error&&<p role="alert">{error}<button type="button" onClick={()=>setRetry(value=>value+1)}>重试目录</button></p>}
      {current?.more&&<button type="button" disabled={loading} onClick={()=>void load(true)}>更早的成果</button>}
      </div>
    </details>
    {selectedKey&&!view&&!detailError&&<p role="status">正在读取所选成果…</p>}
    {detailError&&<p role="alert">{detailError}<button type="button" onClick={()=>setRetry(value=>value+1)}>重新读取成果</button></p>}
    {error&&fallback&&<details open><summary>原有目录（兼容读取）</summary>{fallback}</details>}
    {view&&<article className="thread-product-view"><header><h3 title={view.entry.title}>{view.entry.title}</h3><span title={Array.isArray(view.entry.source.delivery_limitations)?view.entry.source.delivery_limitations.filter(item=>typeof item==='string').join('\n'):undefined}>{view.entry.ref.revision?`v${view.entry.ref.revision} · `:''}{productStatus(view.entry)}</span></header>
      <div className="thread-product-actions">{onReference&&<button type="button" aria-label="引用到下一轮" disabled={!view.entry.capabilities.select} title={view.entry.capabilities.select?'引用到下一轮':productSelectionReason(view.entry.selection_unavailable_reason)} onClick={()=>onReference(view.entry)}><ArrowUpRight aria-hidden="true"/><span>引用到下一轮</span></button>}
        {onReference&&!view.entry.capabilities.select&&view.entry.capabilities.select_excerpt&&<button type="button" onClick={()=>onReference(view.entry,{max_bytes:applicationCapacity('product_excerpt_bytes')})}>引用开头摘录（最多{Math.ceil(applicationCapacity('product_excerpt_bytes')/1024)}KiB）</button>}
        {view.entry.ref.attempt_id&&onLocate&&<button type="button" aria-label="定位指令" title="定位指令" onClick={()=>onLocate(view.entry.ref.attempt_id!)}><LocateFixed aria-hidden="true"/><span>定位指令</span></button>}
        {view.entry.ref.attempt_id&&onInspect&&<button type="button" aria-label="执行详情" title="执行详情" onClick={()=>onInspect(view.entry.ref.attempt_id!)}><ListTree aria-hidden="true"/><span>执行详情</span></button>}
        {view.entry.ref.origin==='native_file'&&onAdopt&&<button type="button" aria-label="作为任务交付" title="作为任务交付" disabled={!view.bytes} onClick={()=>onAdopt(parseNativeArtifact(view.entry.source,threadId,view.entry.ref.attempt_id!))}><FileCheck aria-hidden="true"/><span>作为任务交付</span></button>}
        {view.bytes&&url&&<a aria-label="下载文件" title="下载文件" href={url} download={typeof view.entry.source.file_name==='string'?view.entry.source.file_name:view.entry.title}><ArrowDownToLine aria-hidden="true"/><span>下载文件</span></a>}
      </div>
      {!view.entry.capabilities.select&&<p>{productSelectionReason(view.entry.selection_unavailable_reason)}</p>}
      {view.projection&&<ResultProjectionCard projection={view.projection} onFocusElement={onFocusElement}/>}
      {view.bytes&&<NativeFileContent previewSize={view.bytes.byteLength} name={fileName} media={previewMedia} url={url} text={text} textUnavailable={textUnavailable}/>}
      {view.record&&<div><p>此项是执行记录，没有文件内容。</p>{typeof view.record.instruction==='string'&&<p>{view.record.instruction}</p>}{typeof view.record.failure_code==='string'&&<p>记录尚未提供可读的原因说明，可查看原指令和执行详情。</p>}</div>}
      {view.entry.dependencies.length>0&&<details><summary>支撑成果 · {view.entry.dependencies.length}</summary>{view.entry.dependencies.map(ref=><button type="button" key={productRefKey(ref)} onClick={()=>setSelection(ref)}>查看支撑{ref.scope==='task'?'交付':'产物'}{ref.revision?` v${ref.revision}`:''}</button>)}</details>}
      <p className="thread-product-history-note">来自已保存历史；引用不会自动成为当前运行的 Authority 证据。</p>
    </article>}
  </section>
}
