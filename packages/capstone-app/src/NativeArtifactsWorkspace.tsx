import {applicationCapacity,exceedsCapacity,observeCapacity,rethrowDebugCapacity,CapacityError} from './applicationCapacity'
import {useEffect,useRef,useState} from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {csvMarkdown} from './csvMarkdown'
import type {NativeArtifact,NativeArtifactPage} from './nativeArtifacts'
import './nativeArtifacts.css'
import PptxPreview from './PptxPreview'
import {useSessionViewState,useSessionObjectUrls,sessionObjectUrl} from './workspaceSessionCache'

type FileClient={
  nativeArtifacts:(threadId:string,attemptId:string,after?:number,signal?:AbortSignal)=>Promise<NativeArtifactPage>
  nativeArtifact:(artifact:NativeArtifact,signal?:AbortSignal)=>Promise<Uint8Array>
}
type Selection={threadId:string;attemptId:string;artifactId:string;requestKey:string}
type Preview={key:string;status:'loading'|'ready'|'error';url?:string;text?:string;textUnavailable?:boolean}
const fileKey=(file:NativeArtifact)=>`${file.thread_id}:${file.attempt_id}:${file.artifact_id}`
const statusNames:Record<string,string>={completed:'已完成',failed:'未完成',cancelled:'已取消',interrupted:'已中断',blocked:'未执行'}

/** A filename fallback affects only the isolated preview, never the stored descriptor. */
export function nativePreviewMedia(name:string,media:string|null|undefined){
  const normalized=media?.split(';')[0].trim().toLowerCase()
  if(normalized&&normalized!=='application/octet-stream')return normalized
  if(/\.html?$/i.test(name))return 'text/html'
  if(/\.svg$/i.test(name))return 'image/svg+xml'
  if(/\.pptx$/i.test(name))return 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  if(/\.csv$/i.test(name))return 'text/csv'
  return normalized||'application/octet-stream'
}
const htmlPreviewPolicy='<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data: blob:; font-src data:; base-uri \'none\'; form-action \'none\'">'

export function htmlPreviewDocument(text:string) {
  const document=new DOMParser().parseFromString(text,'text/html')
  // srcDoc inherits the App base URL. Bind local links to the preview document
  // without giving the sandbox script or same-origin access.
  for(const link of document.querySelectorAll('a[href]')){
    const href=link.getAttribute('href')?.trim()
    if(href?.startsWith('#')){link.setAttribute('href',`about:srcdoc${href}`);link.removeAttribute('target')}
  }
  document.head.insertAdjacentHTML('afterbegin',htmlPreviewPolicy+'<style>html{scroll-behavior:smooth}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}</style>')
  return '<!doctype html>'+document.documentElement.outerHTML
}

/** Shared rendering for authenticated, verified persisted file bytes. */
export function NativeFileContent({name,media,url,text,textUnavailable,previewSize}:{name:string;media:string;url?:string;text?:string;textUnavailable?:boolean;previewSize?:number}) {
  if(previewSize!==undefined)observeCapacity(previewSize,'preview_bytes','artifact.preview')
  const csv=media==='text/csv'&&text!==undefined&&!textUnavailable&&(previewSize===undefined||previewSize<=applicationCapacity('preview_bytes'))?csvMarkdown(text):undefined;
  return <div className="native-artifact-preview">{previewSize!==undefined&&previewSize>applicationCapacity('preview_bytes')?<p>此文件超过内置预览容量（{applicationCapacity('preview_bytes')} 字节），可下载完整文件。</p>:textUnavailable?<p>此文件无法按 UTF-8 文本预览，可下载后查看。</p>
    :media==='text/html'?<iframe title={`HTML 预览：${name}`} sandbox="" referrerPolicy="no-referrer" srcDoc={htmlPreviewDocument(text||'')}/>
    :media==='text/markdown'?<div className="capstone-chat-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{img:({alt})=><span>{alt?`图片引用：${alt}`:'外部图片引用'}</span>,a:({href,children})=><a href={href} target="_blank" rel="noopener noreferrer">{children}</a>}}>{text||''}</ReactMarkdown></div>
    :csv?<div className="capstone-chat-markdown capstone-chat-table-scroll native-csv-preview"><ReactMarkdown remarkPlugins={[remarkGfm]}>{csv.markdown}</ReactMarkdown>{csv.truncated&&<p>预览最多显示 500 行数据、100 列；下载可查看完整 CSV。</p>}</div>
    :text!==undefined?<pre>{text}</pre>
    :['image/png','image/jpeg','image/svg+xml'].includes(media)?<img src={url} alt={name}/>
    :media==='application/pdf'?<iframe src={url} title={`PDF 预览：${name}`} sandbox="" referrerPolicy="no-referrer"/>
    :media==='application/vnd.openxmlformats-officedocument.presentationml.presentation'?<PptxPreview key={url} name={name} url={url}/>
    :<p>此文件格式没有内置预览，可下载后查看。</p>}</div>
}

/** An authenticated reader supplies verified bytes. This view never executes or promotes files. */
export default function NativeArtifactsWorkspace({client,threadId,attemptIds,revision,requestedArtifact,attemptLabels,onAdopt}: {
  client:FileClient;threadId:string;attemptIds:readonly string[];revision:number
  requestedArtifact?:{attemptId:string;artifactId:string;nonce?:number}
  attemptLabels?:Readonly<Record<string,string>>
  onAdopt?:(artifact:NativeArtifact)=>void
}) {
  const [directory,setDirectory]=useState<{thread:string;files:NativeArtifact[]}>({thread:threadId,files:[]})
  const [selection,setSelection]=useSessionViewState<Selection|undefined>('files.selection',undefined)
  const [preview,setPreview]=useState<Preview>()
  const [fatalError,setFatalError]=useState<CapacityError>()
  const [loading,setLoading]=useState(false)
  const [directoryError,setDirectoryError]=useState(false)
  const [reload,setReload]=useState(0)
  const [contentReload,setContentReload]=useState(0)
  const sessionUrls=useSessionObjectUrls()
  const [more,setMore]=useState<Record<string,number>>({})
  const requests=useRef<AbortController|undefined>(undefined)
  const generation=useRef(0)
  const cursor=useRef<Record<string,number>>({})
  const clientRef=useRef(client)
  clientRef.current=client
  const requestKey=JSON.stringify(requestedArtifact||null)
  const attemptsKey=JSON.stringify([...new Set([...attemptIds,...(requestedArtifact?[requestedArtifact.attemptId]:[])])])
  const files=directory.thread===threadId?directory.files:[]
  const target=selection?.threadId===threadId&&selection.requestKey===requestKey?selection:requestedArtifact
  const chosen=target?files.find(file=>target.attemptId===file.attempt_id&&target.artifactId===file.artifact_id):files[0]
  const chosenKey=chosen?fileKey(chosen):undefined

  async function load(older=false) {
    if(fatalError)return
    requests.current?.abort()
    const controller=new AbortController()
    requests.current=controller
    const current=++generation.current
    const attempts=JSON.parse(attemptsKey) as string[]
    setLoading(true);setDirectoryError(false)
    const loaded:NativeArtifact[]=[]
    const remaining:Record<string,number>={}
    let failed=false
    // Keep host pressure bounded. Empty Attempt-record pages still advance the same cursor.
    for(const attempt of attempts){
      if(controller.signal.aborted)return
      if(older&&cursor.current[attempt]===undefined)continue
      let after=older?cursor.current[attempt]:0
      try{
        for(let pageNumber=0;pageNumber<applicationCapacity('artifact_initial_pages');pageNumber++){
          const page=await clientRef.current.nativeArtifacts(threadId,attempt,after,controller.signal)
          if(controller.signal.aborted||current!==generation.current)return
          loaded.push(...page.artifacts.filter(file=>file.thread_id===threadId&&file.attempt_id===attempt))
          if(page.hasMore)remaining[attempt]=page.nextAfter
          else delete remaining[attempt]
          const sought=requestedArtifact?.attemptId===attempt?requestedArtifact.artifactId:undefined
          if(!page.hasMore||(sought?page.artifacts.some(file=>file.artifact_id===sought):page.artifacts.length>0))break
          if(pageNumber+1===applicationCapacity('artifact_initial_pages'))observeCapacity(pageNumber+2,'artifact_initial_pages','artifact.initial-scan')
          after=page.nextAfter
        }
      }catch(error){if(error instanceof CapacityError&&error.fatal){setFatalError(error);return}rethrowDebugCapacity(error);if(controller.signal.aborted)return;failed=true;if(older&&cursor.current[attempt]!==undefined)remaining[attempt]=cursor.current[attempt]}
    }
    if(controller.signal.aborted||current!==generation.current)return
    setDirectory(previous=>({thread:threadId,files:[...new Map([...(previous.thread===threadId?previous.files:[]),...loaded].map(file=>[fileKey(file),file])).values()]}))
    cursor.current=remaining;setMore(remaining);setDirectoryError(failed);setLoading(false)
  }
  useEffect(()=>{
    cursor.current={};setMore({})
    void load()
    return()=>{generation.current++;requests.current?.abort()}
    // Directory updates do not reset the selected file or its reading position.
  },[threadId,attemptsKey,revision,reload,requestKey])
  useEffect(()=>{
    if(!chosen||!chosenKey)return
    if(sessionUrls&&preview?.key===chosenKey&&preview.status==='ready'&&sessionUrls.has(`native:${chosenKey}`)&&contentReload===0)return
    const controller=new AbortController()
    let live=true,objectUrl:string|undefined
    setPreview({key:chosenKey,status:'loading'})
    void clientRef.current.nativeArtifact(chosen,controller.signal).then(bytes=>{
      if(!live||controller.signal.aborted)return
      if(bytes.byteLength!==chosen.size_bytes||exceedsCapacity(bytes.byteLength,'artifact_file_bytes'))throw new Error('文件内容大小不一致')
      const media=nativePreviewMedia(chosen.file_name,chosen.media_type)
      const isText=media.startsWith('text/')||media==='application/json'
      let text:string|undefined,textUnavailable=false
      observeCapacity(bytes.byteLength,'preview_bytes','artifact.preview')
      if(isText&&bytes.byteLength<=applicationCapacity('preview_bytes')){try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes)}catch{textUnavailable=true}}
      objectUrl=sessionObjectUrl(sessionUrls,'native',chosenKey,bytes,media)
      setPreview({key:chosenKey,status:'ready',url:objectUrl,text,textUnavailable})
    }).catch(error=>{if(error instanceof CapacityError&&error.fatal){setFatalError(error);return}rethrowDebugCapacity(error);if(live&&!controller.signal.aborted)setPreview({key:chosenKey,status:'error'})})
    return()=>{live=false;controller.abort();if(objectUrl&&!sessionUrls)URL.revokeObjectURL(objectUrl)}
  },[chosenKey,chosen?.sha256,contentReload])
  const currentPreview=preview?.key===chosenKey?preview:undefined
  if(fatalError)return <p role="alert">{fatalError.message}</p>
  return <section className="native-artifacts-workspace" aria-label="指令文件">
    <header><h3>指令文件</h3><p>执行中实际生成并保存的文件，保留各次执行的归属。</p></header>
    {files.length>0&&<ul className="native-artifact-list" aria-label="已保存文件">{files.map(file=><li key={fileKey(file)}><button type="button" aria-label={file.file_name} aria-pressed={fileKey(file)===chosenKey} title={attemptLabels?.[file.attempt_id]||file.file_name}
      onClick={()=>setSelection({threadId,attemptId:file.attempt_id,artifactId:file.artifact_id,requestKey})}><span>{file.file_name}</span><small>{statusNames[file.source_status]||'执行记录'} · {Math.ceil(file.size_bytes/1024)} KB</small>{attemptLabels?.[file.attempt_id]&&<small className="native-artifact-origin">{attemptLabels[file.attempt_id]}</small>}</button></li>)}</ul>}
    {!loading&&!files.length&&!directoryError&&<p>尚无已保存的指令文件。</p>}
    {directoryError&&<p role="alert">部分文件目录暂时无法读取，已加载文件仍可查看。</p>}
    {loading&&<p role="status">正在读取指令文件…</p>}
    {!loading&&target&&!chosen&&!directoryError&&<p role="status">所选文件尚未加载，可继续读取更多文件。</p>}
    {(Object.keys(more).length>0||directoryError)&&<button type="button" className="thread-control-button" disabled={loading} onClick={()=>directoryError?setReload(value=>value+1):void load(true)}>{directoryError?'重新读取目录':'更多文件'}</button>}
    {chosen&&<article className="native-artifact-view" aria-label={`文件预览：${chosen.file_name}`}>
      <header><div><h4>{chosen.file_name}</h4>{attemptLabels?.[chosen.attempt_id]&&<p>{attemptLabels[chosen.attempt_id]}</p>}</div>{currentPreview?.status==='ready'&&<div className="native-artifact-actions"><a href={currentPreview.url} download={chosen.file_name}>下载文件</a>{onAdopt&&<button type="button" className="thread-control-button" onClick={()=>onAdopt(chosen)}>作为任务交付</button>}</div>}</header>
      {(!currentPreview||currentPreview.status==='loading')&&<p role="status">正在读取已保存内容…</p>}
      {currentPreview?.status==='error'&&<div role="alert"><p>文件内容暂时无法读取。生成记录已保留，可重新读取。</p><button type="button" onClick={()=>setContentReload(value=>value+1)}>重新读取文件</button></div>}
      {currentPreview?.status==='ready'&&<NativeFileContent previewSize={chosen.size_bytes} name={chosen.file_name} media={nativePreviewMedia(chosen.file_name,chosen.media_type)} url={currentPreview.url} text={currentPreview.text} textUnavailable={currentPreview.textUnavailable}/>}
      <details><summary>文件信息</summary><dl><dt>所属执行</dt><dd>{chosen.attempt_id}</dd><dt>内容校验</dt><dd>{chosen.sha256}</dd><dt>文件大小</dt><dd>{chosen.size_bytes} bytes</dd></dl></details>
    </article>}
  </section>
}
