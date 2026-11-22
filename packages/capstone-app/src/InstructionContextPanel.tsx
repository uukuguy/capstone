import {useEffect,useRef,useState} from 'react'
import {Crosshair,Layers,Scissors} from 'lucide-react'
import {contextCachePercent,contextCategories,contextPercent,contextTokenLabel as tokens,type ContextObservation,type Category} from './instructionContext'
import RequestContextEntries, {type ReadRequestContext} from './RequestContextEntries'
import './instructionContext.css'

const stateLabels:Record<string,string>={started:'进行中',completed:'已完成',failed:'失败',cancelled:'已取消',skipped:'已跳过'}
const reasons:Record<string,string>={threshold:'达到压缩阈值',overflow:'超过上下文限制',manual:'手动压缩',unknown:'原因未记录'}
const usageLabels={input:'未缓存输入',cacheRead:'缓存读取',cacheWrite:'缓存写入',output:'输出'} as const

export function contextIndicator(row?:ContextObservation) {
  if(row?.inputTokens===undefined)return '未记录'
  const percent=contextPercent(row)
  return `${tokens(row.inputTokens)}${row.windowTokens!==undefined?` / ${tokens(row.windowTokens)}`: ' token'}${percent!==undefined?` · ${percent}%`:''}${row.basis==='estimate'?' · 估算':''}`
}

function rowTitle(row:ContextObservation) {
  return row.kind==='compaction'?'上下文压缩':row.kind==='analysis'?'分析调用':row.kind==='summary'?'压缩调用':'模型调用'
}

export default function InstructionContextPanel({rows,attempt,requested,labels,onShowSession,onLocate,onLocateRequest,onScope,onSelection,readToolExcerpt,readSnapshot}:{
  rows:readonly ContextObservation[]
  attempt?:string
  requested?:{id:string;nonce:number}
  labels:Record<string,string>
  onShowSession:()=>void
  onLocate:(attemptId:string)=>void
  readSnapshot?:ReadRequestContext
  onLocateRequest?:(attemptId:string,dispatchId:string)=>void
  onScope:(attempt?:string)=>void
  readToolExcerpt?:(sourceId:string,attemptId:string)=>string|undefined
  onSelection:(selection?:{attemptId:string;label:string;dispatchId?:string})=>void
}){
  const detailRef=useRef<HTMLElement>(null)
  const [selection,setSelection]=useState<{id:string;scope?:string}>()
  const [category,setCategory]=useState<{request:string;id:Category}>()
  const [visibleCount,setVisibleCount]=useState(12)
  const [loadedSnapshot,setLoadedSnapshot]=useState<string>()
  const [allItemsKey,setAllItemsKey]=useState<string>()
  const instruction=attempt && rows.find(row=>row.attemptId===attempt)?.instructionId
  const shown=attempt ? rows.filter(row=>instruction ? row.instructionId===instruction : row.attemptId===attempt) : rows
  const latest=shown.filter(row=>row.kind==='main').at(-1)??shown.at(-1)
  useEffect(()=>{
    if(!requested)return
    setSelection({id:requested.id,scope:attempt})
    requestAnimationFrame(()=>detailRef.current?.scrollIntoView?.({block:'nearest'}))
  },[requested,attempt])
  const current=(selection?.scope===attempt&&shown.find(row=>row.id===selection?.id))||latest
  const canReadSnapshot=Boolean(readSnapshot)
  useEffect(()=>setLoadedSnapshot(undefined),[current?.snapshotRef,canReadSnapshot])
  const modelCalls=shown.filter(row=>row.kind!=='compaction')
  const series=modelCalls.slice(-12)
  const maxInput=Math.max(1,...series.map(row=>row.inputTokens??0))
  const description=(value?:string)=>value?.replace(/\s+/g,' ').slice(0,180)
  const attempts=[...new Set(shown.map(row=>row.attemptId))]
  const instructions=[...new Map(rows.map(row=>[row.instructionId,row.attemptId])).entries()].reverse()
  const instructionSummaries=new Map(rows.flatMap(row=>labels[row.attemptId]?[[row.instructionId,description(labels[row.attemptId])]] as const:[]))
  const ordinal=new Map(modelCalls.map((row,index)=>[row.id,index+1]))
  function select(id:string) {
    setSelection({id,scope:attempt})
    requestAnimationFrame(()=>detailRef.current?.scrollIntoView?.({block:'nearest'}))
  }
  const numberedTitle=(row:ContextObservation)=>row.kind==='compaction'?rowTitle(row):`${rowTitle(row)} ${ordinal.get(row.id)}`
  const linkedAttempt=current?.attemptId
  const linkedDispatch=current?.dispatchId
  const linkedTitle=current&&numberedTitle(current)
  useEffect(()=>{
    onSelection(linkedAttempt&&linkedTitle?{attemptId:linkedAttempt,label:linkedTitle,dispatchId:linkedDispatch}:undefined)
  },[linkedAttempt,linkedTitle,linkedDispatch,onSelection])
  const label=(row:ContextObservation)=>`${numberedTitle(row)} · ${row.kind==='compaction'?(reasons[row.reason??'unknown']??reasons.unknown):contextIndicator(row)}`
  const list=shown.slice(-visibleCount)
  const compactionCalls=current?.kind==='compaction'
    ? shown.filter(row=>row.attemptId===current.attemptId&&row.taskId===current.taskId&&row.kind!=='compaction')
    : []
  const beforeCompaction=current?.kind==='compaction'
    ? compactionCalls.filter(row=>row.kind==='main'&&row.sequence<current.sequence).at(-1)
    : undefined
  const summaryCalls=current?.kind==='compaction'&&current.compactionEndSequence!==undefined
    ? compactionCalls.filter(row=>row.kind==='summary'&&row.sequence>current.sequence&&row.sequence<=current.compactionEndSequence!)
    : []
  const nextMain=current?.kind==='compaction'&&current.state==='completed'&&current.compactionEndSequence!==undefined
    ? compactionCalls.find(row=>row.kind==='main'&&row.sequence>current.compactionEndSequence!)
    : undefined
  const previousCapture=current&&rows.filter(row=>row.sequence<current.sequence&&row.instructionId===current.instructionId
    &&row.attemptId===current.attemptId&&row.taskId===current.taskId&&row.kind===current.kind&&row.snapshotRef).at(-1)
  const occupancy=current&&contextPercent(current)
  const cachePercent=current&&contextCachePercent(current)
  const categories=(Object.keys(contextCategories) as Category[]).flatMap(id=>{
    const name=contextCategories[id]
    const value=current?.categories?.[id as keyof typeof contextCategories]
    return value===undefined?[]:[{id,name,value}]
  })
  const selectedCategory=category?.request===current?.id?categories.find(row=>row.id===category?.id):undefined
  const breakdownTotal=categories.reduce((sum,row)=>sum+row.value,0)

  const categoryTitle=(row:typeof categories[number])=>`${row.name} · ${row.value.toLocaleString('zh-CN')} token · 估算`
  const chooseCategory=(id:Category)=>{if(current)setCategory({request:current.id,id})}
  const itemLabels:Record<string,string>={system:'系统提示',tool:'工具定义',user:'用户消息',assistant:'模型消息',message:'会话消息',toolResult:'工具返回'}
  const displayedItems=(Object.keys(contextCategories) as Category[]).flatMap(id=>
    [...(current?.items?.[id]?.items??[])].sort((left,right)=>left.index-right.index).map(item=>({id,item})))
    .filter(row=>!selectedCategory||row.id===selectedCategory.id)
  const itemsKey=`${current?.id??''}:${selectedCategory?.id??''}`
  const visibleItems=allItemsKey===itemsKey?displayedItems:displayedItems.slice(0,8)
  const itemCount=selectedCategory?(current?.items?.[selectedCategory.id]?.total??0):
    Object.values(current?.items??{}).reduce((sum,group)=>sum+group.total,0)

  return <section className="context-inspector" aria-label="上下文观察">
    <header className="context-inspector-heading">
      <div className="context-scope"><Layers aria-hidden="true" size={15}/>{attempt?'本条指令':'当前会话'}</div>
      {attempt&&<button type="button" onClick={onShowSession}>查看会话</button>}
    </header>
    {instructions.length>0&&<label className="context-instruction-filter">
      <span>指令</span>
      <select aria-label="按指令查看上下文" value={instruction||''} onChange={event=>onScope(instructions.find(([id])=>id===event.target.value)?.[1])}>
        <option value="">全部指令</option>
        {instructions.map(([id],index)=><option key={id} value={id}>{instructionSummaries.get(id)??`历史指令 ${instructions.length-index}`}</option>)}
      </select>
    </label>}
    {!shown.length&&<p className="context-empty">当前范围暂无调用记录。执行指令后可在这里查看。</p>}
    {shown.length>0&&<div className="context-inspector-body">
      {current&&<section ref={detailRef} className="context-detail" aria-label="所选记录">
        <div className="context-section-title"><h3>{numberedTitle(current)}</h3><span>{stateLabels[current.state]||current.state}</span>
          {current.dispatchId&&onLocateRequest&&<button className="context-locate-request" type="button" onClick={()=>onLocateRequest(current.attemptId,current.dispatchId!)}><Crosshair size={14} aria-hidden="true"/>定位执行记录</button>}
        </div>
        {current.kind==='compaction'?<>
          <p>{reasons[current.reason??'unknown']??reasons.unknown}</p>
          <dl><div><dt>压缩前占用</dt><dd>{current.inputTokens===undefined?'未记录':`${tokens(current.inputTokens)} token · SDK 估算`}</dd></div>
          </dl>
          <div className="context-source-filters" aria-label="压缩关联请求">
            {beforeCompaction&&<button type="button" onClick={()=>select(beforeCompaction.id)}>压缩前请求</button>}
            {summaryCalls.map((summary,index)=><button type="button" key={summary.id}
              onClick={()=>select(summary.id)}>摘要请求{summaryCalls.length>1?` ${index+1}`:''}</button>)}
            {nextMain&&<button type="button" onClick={()=>select(nextMain.id)}>压缩后首个请求</button>}
          </div>
          {current.firstKeptEntryId&&<details><summary>保留边界</summary><code>{current.firstKeptEntryId}</code></details>}
        </>:<>
          <div className="context-metrics">
            <div><span>已用上下文</span><div><strong>{current.inputTokens===undefined?'未记录':tokens(current.inputTokens)}</strong>{current.windowTokens!==undefined&&<small> / {tokens(current.windowTokens)} token</small>}</div>
              <small>{current.basis==='provider'?'Provider 回执':current.basis==='estimate'?'估算':''}{occupancy!==undefined&&` · ${occupancy}%`}</small>
          {occupancy!==undefined&&<div className="context-window-meter" role="meter" aria-label="请求输入占模型窗口比例"
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(100,occupancy)} aria-valuetext={`${occupancy}%`}>
            <i style={{width:`${Math.min(100,occupancy)}%`}} />
          </div>}
            </div>
            {cachePercent!==undefined&&
              <div><span>输入缓存命中</span><div><strong>{cachePercent.toFixed(1)}%</strong></div><small>{tokens(current.usage?.cacheRead??0)} token 来自缓存</small></div>}
          </div>
          {categories.length>0&&<><h4 title="按发送前的文本与工具结构估算，不含媒体与 Provider 封装。">输入构成 · 估算</h4>
            {breakdownTotal>0&&<div className="context-composition" aria-label="输入构成图">
              {categories.filter(row=>row.value>0).map(row=><button key={row.id} type="button" data-category={row.id}
                style={{flex:row.value}} title={categoryTitle(row)} aria-label={categoryTitle(row)}
                aria-pressed={selectedCategory?.id===row.id} onClick={()=>chooseCategory(row.id)}>
                <small className="context-category-tip" aria-hidden="true">{categoryTitle(row)}</small>
              </button>)}
            </div>}
            <div className="context-category-list" aria-label="输入分类">
              {categories.map(row=><button key={row.id} type="button" aria-expanded={selectedCategory?.id===row.id}
                onClick={()=>chooseCategory(row.id)} title={categoryTitle(row)}>
                <i className="context-category-dot" data-category={row.id}/><span>{row.name}</span><span>{tokens(row.value)}</span>
                <small className="context-category-tip" aria-hidden="true">{categoryTitle(row)}{breakdownTotal>0?` · 构成占比 ${Math.round(row.value/breakdownTotal*100)}%`:''}</small>
              </button>)}
            </div>
          </>}
          {current.snapshotRef&&readSnapshot&&<RequestContextEntries key={current.snapshotRef}
            attempt={current.attemptId} snapshot={current.snapshotRef} previous={previousCapture?.snapshotRef} category={selectedCategory?.id} read={readSnapshot}
            onResetCategory={()=>setCategory(undefined)} onIndexReady={()=>setLoadedSnapshot(current.snapshotRef)}/>}
            {categories.length>0&&(!current.snapshotRef||loadedSnapshot!==current.snapshotRef)&&<section className="context-category-detail" aria-label={selectedCategory?selectedCategory.name+'详情':'输入内容'}>
              <div className="context-section-title"><h4>用量摘要</h4>{selectedCategory&&<button type="button" onClick={()=>setCategory(undefined)}>显示全部分类</button>}</div>
              {displayedItems.length?<ul className="context-content-items">{visibleItems.map(({id,item})=>{
                const excerpt=item.sourceId&&current?readToolExcerpt?.(item.sourceId,current.attemptId):undefined
                const title=<><i className="context-category-dot" data-category={id}/><span>{item.name??itemLabels[item.kind]}{id==='messages'&&` ${item.index}`}</span><small>{tokens(item.tokens)}</small></>
                return <li key={id+':'+item.index}>{excerpt?<details><summary>{title}</summary><small>已保存的工具返回片段</small><pre>{excerpt}</pre></details>:<div className="context-item-static" title="此请求未记录可读正文">{title}</div>}</li>
              })}</ul>:<p>此请求未记录条目。</p>}
              {visibleItems.length<displayedItems.length&&<button className="context-show-items" type="button" onClick={()=>setAllItemsKey(itemsKey)}>查看已记录的 {displayedItems.length} 项</button>}
              {displayedItems.length<itemCount&&<small>已记录 {displayedItems.length} / {itemCount} 项</small>}
            </section>}
          {!!Object.keys(current.usage??{}).length&&<details><summary>Provider 用量明细</summary><dl>
            {Object.entries(usageLabels).map(([id,name])=>{
              const value=current.usage?.[id as keyof typeof usageLabels]
              return value===undefined?null:<div key={id}><dt>{name}</dt><dd>{tokens(value)}</dd></div>
            })}
          </dl></details>}
        </>}
        <div className="context-detail-source">
          {!attempt&&labels[current.attemptId]&&<p title={description(labels[current.attemptId])}>{description(labels[current.attemptId])}</p>}
          <button type="button" onClick={()=>onLocate(current.attemptId)}>定位指令</button>
        </div>
      </section>}
    {series.length>0&&<div className="context-trend" aria-label="最近请求输入趋势">
      {series.map(row=><button key={row.id} type="button" aria-label={label(row)}
        aria-pressed={row.id===current?.id} onClick={()=>select(row.id)}>
        <span className={row.inputTokens===undefined?'unknown':row.basis}
          style={{height:`${row.inputTokens===undefined?8:Math.max(5,row.inputTokens/maxInput*100)}%`}} /><span className="context-tip" aria-hidden="true">{label(row)}</span>
      </button>)}
    </div>}
      <details className="context-history" aria-label="调用与压缩时间线"><summary>调用历史 · {modelCalls.length} 次{shown.length>modelCalls.length&&` · 压缩 ${shown.length-modelCalls.length} 次`}</summary>
        <div className="context-section-title"><h3>调用与压缩</h3>{shown.length>visibleCount&&<button type="button" onClick={()=>setVisibleCount(visibleCount+12)}>显示更早记录</button>}</div>
        <ol className="context-timeline">{list.map(row=>{
          const retry=attempts.length>1?attempts.indexOf(row.attemptId)+1:0
          return <li key={row.id}>
            <button type="button" className={row.kind==='compaction'?'is-compaction':undefined}
              aria-pressed={current?.id===row.id} title={label(row)} onClick={()=>select(row.id)}>
              {row.kind==='compaction'?<Scissors aria-hidden="true" size={14}/>:<span className="context-timeline-dot" aria-hidden="true"/>}
              <span>{numberedTitle(row)}{retry>0&&attempt&&<small>第 {retry} 次执行</small>}{!attempt&&instructionSummaries.get(row.instructionId)&&<small className="context-row-instruction">{instructionSummaries.get(row.instructionId)}</small>}</span>
              <small>{row.kind==='compaction'?stateLabels[row.state]||row.state:row.inputTokens===undefined?'未记录':tokens(row.inputTokens)+(row.basis==='estimate'?' 估算':'')}</small>
            </button>
          </li>
        })}</ol>
      </details>
    </div>}
  </section>
}
