import {useEffect,useRef,useState} from 'react'
import {productRefKey,type ProductEntry,type ProductRef,type ContextProductRef} from './threadProducts'
import type {SeriesClient,ProductSeries,Comparison,SeriesCommand} from './productSeries'
import {comparisonLines} from './productSeries'

/** User decisions stay outside the composer and never rewrite saved references. */
export default function ProductComparison({client,entry,items,onOpen}:{client:SeriesClient;entry:ProductEntry;items:ProductEntry[];onOpen:(ref:ProductRef)=>void}){
 const [series,setSeries]=useState<ProductSeries|null>(),[sources,setSources]=useState<ContextProductRef[]>([])
 const [members,setMembers]=useState<ProductRef[]>([]),[cursor,setCursor]=useState<string|null>(null)
 const [original,setOriginal]=useState(''),[comparison,setComparison]=useState<Comparison>(),[error,setError]=useState(''),[busy,setBusy]=useState(false)
 const pending=useRef<SeriesCommand|null>(null)
 const key=productRefKey(entry.ref)
 useEffect(()=>{
  const abort=new AbortController();setSeries(undefined);setSources([]);setMembers([]);setComparison(undefined);setError('');setOriginal('')
  void Promise.all([client.discoverProductSeries(entry.ref,abort.signal),client.productSources(entry.ref,abort.signal)]).then(async([state,inputs])=>{
   if(abort.signal.aborted)return
   setSeries(state);setSources(inputs)
   if(state){const page=await client.seriesMembers(entry.ref.thread_id,state.series_id,undefined,abort.signal);if(!abort.signal.aborted){setMembers(page.members);setCursor(page.next_cursor)}}
  }).catch(cause=>{if(!abort.signal.aborted)setError(cause instanceof Error?cause.message:'版本信息读取失败。')})
  return()=>abort.abort()
 },[client,key])
 const candidates=[...new Map([...items.map(item=>item.ref),...members].filter(ref=>productRefKey(ref)!==key).map(ref=>[productRefKey(ref),ref])).values()]
 const label=(ref:ProductRef)=>`${items.find(item=>productRefKey(item.ref)===productRefKey(ref))?.title??ref.product_id} · ${ref.digest.slice(0,8)} · ${ref.product_id}`
 const selected=original===''?undefined:candidates[Number(original)]
 async function action(run:()=>Promise<void>){setBusy(true);setError('');try{await run()}catch(cause){if((cause as {status?:number}).status===409){try{setSeries(await client.discoverProductSeries(entry.ref))}catch{/* Keep the last readable state. */}setError('系列已被更新。请读取当前状态后重新决定。')}else setError(cause instanceof Error?cause.message:'操作失败，请重试。')}finally{setBusy(false)}}
 async function command(operation:SeriesCommand['operation'],state:ProductSeries|null=series??null,product:ProductRef|null=entry.ref){
  const prior=pending.current
  const same=prior&&prior.operation===operation&&prior.expected_revision===(state?.revision??0)&&(!state||prior.series_id===state.series_id)&&JSON.stringify(prior.product)===JSON.stringify(product)
  const id=crypto.randomUUID(),request=same?prior:{schema:'capstone-product-series-command/1' as const,series_id:state?.series_id??crypto.randomUUID(),expected_revision:state?.revision??0,operation,product,command_id:id,idempotency_key:id}
  pending.current=request
  let result:ProductSeries
  try{result=await client.commandProductSeries(entry.ref.thread_id,request)}catch(cause){if((cause as {status?:number}).status===409)pending.current=null;throw cause}
  pending.current=null;setSeries(result);setMembers(result.members)
 }
 return <section className="product-comparison" aria-label="成果对照与采用">
  <h4>成果对照与采用</h4>
  <p>{series===undefined?'正在读取系列…':series?`系列 ${series.series_id} · 修订 ${series.revision}`:'尚未登记系列'}</p>
  {series&&<p role="status">{series.adopted_ref?`当前采用：${label(series.adopted_ref)}`:'尚未采用任何版本'}</p>}
  <div className="thread-product-actions">
   {series===null&&<button disabled={busy} type="button" onClick={()=>void action(()=>command('register'))}>以当前稿建立系列</button>}
   {series&&<><button disabled={busy||!!series.adopted_ref&&productRefKey(series.adopted_ref)===key} type="button" onClick={()=>void action(()=>command('adopt'))}>{series.adopted_ref?'改用当前稿':'采用当前稿'}</button><button disabled={busy||!series.adopted_ref} type="button" onClick={()=>void action(()=>command('clear',series,null))}>清除采用</button></>}
  </div>
  <label>选择原稿<select aria-label="选择原稿" value={original} disabled={busy} onChange={event=>{setOriginal(event.target.value);setComparison(undefined)}}><option value="">请选择一个明确版本</option>{candidates.map((ref,index)=><option key={productRefKey(ref)} value={index}>{label(ref)}</option>)}</select></label>
  <div className="thread-product-actions">
   <button type="button" disabled={busy||!selected} onClick={()=>void action(async()=>setComparison(await client.compareProducts(selected!,entry.ref)))}>对照原稿与当前稿</button>
   {series===null&&<button type="button" disabled={busy||!selected} onClick={()=>void action(async()=>{const existing=await client.discoverProductSeries(selected!);if(!existing)throw new Error('请先打开原稿并建立系列，再关联当前稿。');await command('register',existing)})}>明确关联到原稿系列</button>}
  </div>
  {busy&&<p role="status">正在处理…</p>}{error&&<p role="alert">{error}</p>}
  {comparison&&<><p>全文文字对照；标记表示文字变化，不证明来源事实。</p><div className="product-comparison-columns">{(['original','revised'] as const).map((side,i)=><section key={side} aria-label={i?'当前稿文字':'原稿文字'}><h5>{i?'当前稿':'原稿'}</h5><pre>{comparison.changes.map((change,index)=>{const range=change[side],text=comparisonLines(i?comparison.revised_text:comparison.original_text).slice(...range).join('');return change.kind==='equal'?<span key={index}>{text}</span>:<mark key={index} data-change={change.kind} title={i?'新增或修改':'删除或修改'}>{text}</mark>})}</pre></section>)}</div></>}
  {members.length>0&&<details><summary>系列版本 · {members.length}</summary>{members.map(ref=><button type="button" key={productRefKey(ref)} onClick={()=>onOpen(ref)}>{label(ref)}</button>)}{cursor&&<button disabled={busy} type="button" onClick={()=>void action(async()=>{const page=await client.seriesMembers(entry.ref.thread_id,series!.series_id,cursor);setMembers(previous=>[...previous,...page.members]);setCursor(page.next_cursor)})}>读取更多版本</button>}</details>}
  <details open={sources.length>0}><summary>实际输入来源 · {sources.length}</summary>{sources.map((source,index)=><div key={index}><button type="button" onClick={()=>onOpen(source.ref)}>查看来源 {index+1}：{label(source.ref)}</button>{source.local_selection&&<small>段落 {source.local_selection.block_id} · {source.local_selection.content_digest.slice(0,8)}</small>}{source.excerpt&&<small>开头摘录，最多 {source.excerpt.max_bytes} 字节</small>}</div>)}<p>来源表示执行时已准入的输入，不证明逐句使用。</p></details>
  <p>采用后如需继续处理，请明确引用该成果。已有指令引用保持原版本。</p>
 </section>
}
