import {createContext,useCallback,useContext,useEffect,useLayoutEffect,useRef,useState,type Dispatch,type SetStateAction,type ReactNode} from 'react'
import {applicationCapacity} from './applicationCapacity'

const LIMIT_KEY='capstone.workspace.memory-sessions'
export const DEFAULT_MEMORY_SESSIONS=10
export const MEMORY_SESSION_LIMITS=[10,20,50] as const
export function isMemorySessionLimit(n:number){return MEMORY_SESSION_LIMITS.some(value=>value===n)}
export function memorySessionLimit(){try{const n=Number(localStorage.getItem(LIMIT_KEY));if(isMemorySessionLimit(n))return n}catch{/* Use default. */}return DEFAULT_MEMORY_SESSIONS}
export function setMemorySessionLimit(n:number){if(!isMemorySessionLimit(n))return;try{localStorage.setItem(LIMIT_KEY,String(n))}catch{/* Keep live value through the event. */}window.dispatchEvent(new CustomEvent('capstone-session-cache-limit',{detail:n}))}
export type SessionVisits=Record<string,{switches:number;lastOpenedAt:number}>
const visitsKey=(namespace:string)=>`capstone.workspace.visits:${namespace}`
export function readSessionVisits(namespace:string):SessionVisits{
  try{
    const raw=localStorage.getItem(visitsKey(namespace));if(!raw||raw.length>131072)return {}
    const value:unknown=JSON.parse(raw);if(!value||typeof value!=='object'||Array.isArray(value))return {}
    const entries=Object.entries(value).flatMap<[string,SessionVisits[string]]>(([id,entry])=>{
      if(!/^[a-z][a-z0-9_-]{0,63}$/.test(id)||!entry||typeof entry!=='object'||Array.isArray(entry))return []
      const {switches,lastOpenedAt}=entry as Record<string,unknown>
      if(typeof switches!=='number'||!Number.isSafeInteger(switches)||switches<0||typeof lastOpenedAt!=='number'||!Number.isFinite(lastOpenedAt)||lastOpenedAt<0)return []
      return [[id,{switches,lastOpenedAt}]]
    })
    return Object.fromEntries(entries.sort((a,b)=>b[1].lastOpenedAt-a[1].lastOpenedAt).slice(0,applicationCapacity('ui_cache_items')))
  }catch{return {}}
}
export function recordSessionVisit(namespace:string,previous:SessionVisits,id:string,now=Date.now()):SessionVisits{
  if(!/^[a-z][a-z0-9_-]{0,63}$/.test(id))return previous
  const next={...previous,[id]:{switches:Math.min(Number.MAX_SAFE_INTEGER,(previous[id]?.switches??0)+1),lastOpenedAt:now}}
  const bounded=Object.fromEntries(Object.entries(next).sort((a,b)=>b[1].lastOpenedAt-a[1].lastOpenedAt).slice(0,applicationCapacity('ui_cache_items')))
  try{localStorage.setItem(visitsKey(namespace),JSON.stringify(bounded))}catch{/* Keep live visit counts. */}
  return bounded
}
/** Frequency decays with a 24-hour half-life; recency breaks ties. Never evict current. */
export function retainSessions(previous:readonly string[],current:string,limit:number,visits:SessionVisits={},now=Date.now()){
  const ids=[...previous.filter(id=>id!==current),current]
  const score=(id:string)=>Math.log2(1+(visits[id]?.switches??0))*2**(-Math.max(0,now-(visits[id]?.lastOpenedAt??now))/86400000)
  const ranked=ids.filter(id=>id!==current).sort((a,b)=>score(b)-score(a)||(visits[b]?.lastOpenedAt??ids.indexOf(b))-(visits[a]?.lastOpenedAt??ids.indexOf(a)))
  const keep=new Set([current,...ranked.slice(0,Math.max(0,limit-1))])
  return ids.filter(id=>keep.has(id))
}
export function SessionCacheSetting(){
  const [limit,setLimit]=useState(memorySessionLimit)
  useEffect(()=>{const changed=(event:Event)=>setLimit((event as CustomEvent<number>).detail);window.addEventListener('capstone-session-cache-limit',changed);return()=>window.removeEventListener('capstone-session-cache-limit',changed)},[])
  return <label className="workspace-cache-setting">内存保留会话<select aria-label="最多同时保留会话" value={limit} onChange={event=>setMemorySessionLimit(Number(event.target.value))}>{MEMORY_SESSION_LIMITS.map(n=><option key={n} value={n}>{n} 个</option>)}</select></label>
}

type ScrollPosition={top:number;left:number}
type ReadingSnapshot={values:Record<string,unknown>;positions:Record<string,ScrollPosition>}
type ReadingStore={snapshot:ReadingSnapshot;save:()=>void;urls:Map<string,string>}
const ReadingContext=createContext<ReadingStore|undefined>(undefined)
function readSnapshot(key:string):ReadingSnapshot{
  try{const raw=localStorage.getItem(key);if(raw&&raw.length<=131072){const value=JSON.parse(raw);if(value?.schema===1&&value.values&&typeof value.values==='object'&&!Array.isArray(value.values)&&value.positions&&typeof value.positions==='object'&&!Array.isArray(value.positions))return {values:value.values,positions:value.positions}}}catch{/* A cache cannot block the host. */}
  return {values:{},positions:{}}
}
/** Only presentation values and offsets go to disk. Products remain host-owned. */
export function SessionReadingProvider({namespace,threadId,children}:{namespace:string;threadId:string;children:ReactNode}){
  const key=`capstone.workspace.reading:${namespace}:${threadId}`
  const [store]=useState<ReadingStore>(()=>({snapshot:readSnapshot(key),urls:new Map(),save(){try{const raw=JSON.stringify({schema:1,...this.snapshot});if(raw.length<=131072)localStorage.setItem(key,raw)}catch{/* Disk quota does not block navigation. */}}}))
  useEffect(()=>()=>{store.save();for(const url of store.urls.values())URL.revokeObjectURL(url);store.urls.clear()},[store])
  return <ReadingContext.Provider value={store}>{children}</ReadingContext.Provider>
}
export function useSessionViewState<T>(name:string,initial:T|(()=>T)):[T,Dispatch<SetStateAction<T>>]{
  const store=useContext(ReadingContext)
  const [value,update]=useState<T>(()=>Object.prototype.hasOwnProperty.call(store?.snapshot.values??{},name)?store!.snapshot.values[name] as T:typeof initial==='function'?(initial as ()=>T)():initial)
  const setValue:Dispatch<SetStateAction<T>>=useCallback(next=>update(previous=>{
    const value=typeof next==='function'?(next as (previous:T)=>T)(previous):next
    if(store){if(value===undefined)delete store.snapshot.values[name];else store.snapshot.values[name]=value;store.save()}
    return value
  }),[store,name])
  return [value,setValue]
}
/** URLs live with the retained session, outside its paused Activity effects. */
export function useSessionObjectUrls(){return useContext(ReadingContext)?.urls}
export function useHasSavedSessionPosition(name:string){return !!useContext(ReadingContext)?.snapshot.positions[`[data-reading-key=${JSON.stringify(name)}]`]}
export function sessionObjectUrl(urls:Map<string,string>|undefined,kind:string,key:string,bytes:Uint8Array,media:string){
  const id=`${kind}:${key}`,cached=urls?.get(id)
  if(cached)return cached
  const url=URL.createObjectURL(new Blob([new Uint8Array(bytes)],{type:media}))
  if(urls){for(const [other,old] of urls)if(other.startsWith(`${kind}:`)){URL.revokeObjectURL(old);urls.delete(other)}urls.set(id,url)}
  return url
}
export function useSessionViewRef<T>(name:string,initial:T){
  const store=useContext(ReadingContext)
  const [ref]=useState(()=>{
    let value=Object.prototype.hasOwnProperty.call(store?.snapshot.values??{},name)?store!.snapshot.values[name] as T:initial
    return {get current(){return value},set current(next:T){value=next;if(store){store.snapshot.values[name]=next;store.save()}}}
  })
  return ref
}

function nodeKey(node:HTMLElement,root:HTMLElement){
  const parts:string[]=[]
  for(let current:HTMLElement|null=node;current&&current!==root;current=current.parentElement){
    const stable=current.dataset.messageId||current.dataset.readingKey
    if(stable){parts.unshift(`[data-${current.dataset.messageId?'message-id':'reading-key'}=${JSON.stringify(stable)}]`);break}
    const index=current.parentElement?[...current.parentElement.children].indexOf(current)+1:1
    parts.unshift(`${current.tagName.toLowerCase()}:nth-child(${index})`)
  }
  return parts.join(' > ')
}
/** Restore offsets after asynchronous history/product content reaches its saved size. */
export function useSessionReadingPositions(root:React.RefObject<HTMLElement|null>){
  const store=useContext(ReadingContext)
  useLayoutEffect(()=>{
    const container=root.current;if(!container||!store)return
    const pending=new Map(Object.entries(store.snapshot.positions)),restoring=new Set<HTMLElement>()
    const restore=()=>{
      for(const [key,position] of pending){
        if(!position||!Number.isFinite(position.top)||!Number.isFinite(position.left)||position.top<0||position.left<0){pending.delete(key);continue}
        let node:HTMLElement|null=null
        try{node=container.querySelector<HTMLElement>(key)}catch{pending.delete(key);continue}
        if(node?.closest('.workspace-navigation')){pending.delete(key);continue}
        if(!node||node.closest('[hidden]'))continue
        restoring.add(node);node.scrollTop=position.top;node.scrollLeft=position.left
        if(Math.abs(node.scrollTop-position.top)<2&&Math.abs(node.scrollLeft-position.left)<2)pending.delete(key)
      }
    }
    const save=(event:Event)=>{const node=event.target;if(!(node instanceof HTMLElement)||node===container||!container.contains(node)||node.closest('.workspace-navigation'))return;const key=nodeKey(node,container);if(restoring.delete(node))return;pending.delete(key);store.snapshot.positions[key]={top:node.scrollTop,left:node.scrollLeft}}
    const cancel=()=>{pending.clear();restoring.clear()}
    container.addEventListener('scroll',save,true);container.addEventListener('wheel',cancel,{passive:true});container.addEventListener('touchstart',cancel,{passive:true})
    const observer=new MutationObserver(restore);observer.observe(container,{childList:true,subtree:true})
    const resize=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(restore);resize?.observe(container)
    const remember=()=>{
      for(const node of container.querySelectorAll<HTMLElement>('*'))if((node.scrollTop||node.scrollLeft)&&!node.closest('.workspace-navigation'))store.snapshot.positions[nodeKey(node,container)]={top:node.scrollTop,left:node.scrollLeft}
      store.save()
    }
    window.addEventListener('pagehide',remember);container.addEventListener('load',restore,true)
    restore()
    return()=>{
      observer.disconnect();resize?.disconnect()
      remember();window.removeEventListener('pagehide',remember);container.removeEventListener('load',restore,true);container.removeEventListener('scroll',save,true);container.removeEventListener('wheel',cancel);container.removeEventListener('touchstart',cancel)
    }
  },[root,store])
}
