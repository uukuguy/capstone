import {applicationCapacity} from './applicationCapacity'
import { useEffect, useRef, useState } from 'react'
import type { CapstoneThreadClient } from './threadClient'
import type { ProcessProduct } from './processProducts'
import AnswerDetailSheet from './AnswerDetailSheet'
import AttemptRecordPanel from './AttemptRecordPanel'
import { readProcessProductResults } from './processProductResults'
import { ResultProjectionCard } from './CapstoneAssistantThread'
import type { ResultProjection } from './threadProtocol'

const labels = {completed:'已完成',failed:'未完成',cancelled:'已取消',interrupted:'已中断'}

/** Session-owned ledger view. It does not promote execution records to deliverables. */
export default function ProcessProductWorkspace({client, threadId, revision, onLocate, onReference}: {
  client: CapstoneThreadClient; threadId:string; revision:number
  onLocate:(attemptId:string)=>void; onReference:(product:ProcessProduct)=>void
}) {
  const [products,setProducts]=useState<ProcessProduct[]>([])
  const [cursor,setCursor]=useState<number>()
  const [more,setMore]=useState(true)
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState(false)
  const [inspect,setInspect]=useState<ProcessProduct>()
  const [selected,setSelected]=useState<ProcessProduct>()
  const [results,setResults]=useState<ResultProjection[]>([])
  const [resultId,setResultId]=useState<string>()
  const [resultState,setResultState]=useState<'loading'|'ready'|'error'>('ready')
  useEffect(()=>{
    if(!selected)return
    const controller=new AbortController()
    setResults([]);setResultId(undefined);setResultState('loading')
    void readProcessProductResults(threadId,selected.attemptId,(id,after)=>client.attemptRecords(threadId,id,after),controller.signal)
      .then(value=>{if(!controller.signal.aborted){setResults(value);setResultState('ready')}})
      .catch(()=>{if(!controller.signal.aborted)setResultState('error')})
    return ()=>controller.abort()
  },[selected,threadId,client])
  const generation=useRef(0)
  const busy=useRef(false)
  const request=useRef<AbortController | null>(null)
  async function load(before?:number) {
    if(busy.current)return
    busy.current=true
    const current=++generation.current
    const controller=new AbortController()
    request.current=controller
    setLoading(true);setError(false)
    try {
      let page=await client.processProducts(threadId,before,controller.signal)
      for(let pages=1;pages<applicationCapacity('artifact_initial_pages') && !page.products.length && page.hasMore;pages++) {
        page=await client.processProducts(threadId,page.nextBefore,controller.signal)
      }
      if(current!==generation.current)return
      setProducts(previous=>before ? [...previous,...page.products.filter(item=>!previous.some(old=>old.productId===item.productId))] : page.products)
      setCursor(page.nextBefore);setMore(page.hasMore)
    } catch {if(current===generation.current)setError(true)}
    finally {if(current===generation.current){busy.current=false;setLoading(false)}}
  }
  useEffect(()=>{
    void load()
    return ()=>{generation.current++;request.current?.abort();busy.current=false}
    // Refresh only after an attempt terminates; streaming events must not reset navigation.
  },[client,threadId,revision])
  return <section className="process-product-workspace" aria-label="过程制品">
    <header><h3>过程制品</h3><p>各条指令的执行结果与未完成记录，可继续引用。</p></header>
    {!loading && !error && products.length===0 && <p>{more?'这一段没有已结束的指令，可继续读取。':'尚无已结束的指令。'}</p>}
    <ol>{products.map(product=><li key={product.productId}>
      <div className="process-product-meta"><span data-status={product.status}>{labels[product.status]}</span><span>{product.modelContext?.modelId || '通用任务'}</span></div>
      <p>{product.instruction}</p>
      <div className="process-product-actions"><button onClick={()=>setSelected({...product})}>查看结果</button><button onClick={()=>onLocate(product.attemptId)}>定位指令</button><button onClick={()=>onReference(product)}>引用到下一轮</button><button onClick={()=>setInspect(product)}>执行记录</button></div>
      {selected?.productId===product.productId && <div aria-live="polite">
        {resultState==='loading' && <p>正在读取已保存结果…</p>}
        {resultState==='error' && <p role="alert">结果暂时无法读取，请重试。</p>}
        {resultState==='ready' && !results.length && <p>本次指令没有已保存的结构化结果，可定位原指令查看回答。</p>}
        {results.length>0 && <><label className="process-result-choice">分析结果<select value={resultId || results[0].resultId} onChange={event=>setResultId(event.target.value)}>{results.map((result,index)=><option key={result.resultId} value={result.resultId}>{index+1}. {result.presentation?.groupTitle || result.modelId} · {result.tables[0]?.title || result.source.capabilityId}{result.status==='partial'?' · 部分结果':''}</option>)}</select></label><ResultProjectionCard key={resultId || results[0].resultId} projection={results.find(result=>result.resultId===resultId) || results[0]} /></>}
      </div>}
    </li>)}</ol>
    {error && <p role="alert">目录暂时无法读取。已加载内容保留。</p>}
    {(more || error) && <button disabled={loading} onClick={()=>void load(cursor)}>{loading?'正在读取…':error?'重试':'更早的指令'}</button>}
    {inspect && <AnswerDetailSheet title="执行记录" answerLabel={inspect.instruction} onClose={()=>setInspect(undefined)}>
      <AttemptRecordPanel key={inspect.attemptId} attemptId={inspect.attemptId} read={(attemptId,after)=>client.attemptRecords(threadId,attemptId,after)} />
    </AnswerDetailSheet>}
  </section>
}
