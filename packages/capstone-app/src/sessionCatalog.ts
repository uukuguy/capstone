import {useEffect,useState,type Dispatch,type SetStateAction} from 'react'
import type {ThreadDescriptor,ThreadListPage} from './threadManagement'
import {applicationCapacity} from './applicationCapacity'

// Read-only presentation cache. It is scoped to the existing access namespace.
// Recovery never clears an already displayed catalog while fetching a new one.
const catalogs=new Map<string,ThreadListPage>()
const reopened=new Map<string,Map<string,ThreadDescriptor>>()
function includeReopened(namespace:string,page:ThreadListPage|null){
  const entries=reopened.get(namespace)
  if(!entries?.size)return page
  const fresh=new Map(page?.threads.map(item=>[item.threadId,item]))
  return {...(page??{hasMore:false,nextBeforeThreadId:null}),threads:[...[...entries.values()].reverse().map(item=>fresh.get(item.threadId)??item),...(page?.threads??[]).filter(item=>!entries.has(item.threadId))]}
}
export function restoreCatalogSession(namespace:string,thread:ThreadDescriptor){
  const entries=reopened.get(namespace)??new Map<string,ThreadDescriptor>()
  entries.delete(thread.threadId);entries.set(thread.threadId,thread)
  while(entries.size>applicationCapacity('ui_session_page_items'))entries.delete(entries.keys().next().value!)
  reopened.set(namespace,entries)
  catalogs.set(namespace,includeReopened(namespace,catalogs.get(namespace)??null)!)
  window.dispatchEvent(new CustomEvent('capstone-session-catalog-changed',{detail:namespace}))
}
export function removeCatalogSession(namespace:string,id:string){
  reopened.get(namespace)?.delete(id)
  const page=catalogs.get(namespace)
  if(page)catalogs.set(namespace,{...page,threads:page.threads.filter(item=>item.threadId!==id)})
  window.dispatchEvent(new CustomEvent('capstone-session-catalog-changed',{detail:namespace}))
}
export function mergeSessionPage(previous:ThreadListPage|null,page:ThreadListPage):ThreadListPage {
  if(!previous||previous.threads.length<=page.threads.length)return page
  const ids=new Set(page.threads.map(item=>item.threadId))
  return {...previous,threads:[...page.threads,...previous.threads.slice(page.threads.length).filter(item=>!ids.has(item.threadId))]}
}
export function useSessionCatalog(namespace:string):[ThreadListPage|null,Dispatch<SetStateAction<ThreadListPage|null>>] {
  const [page,setPage]=useState(()=>includeReopened(namespace,catalogs.get(namespace)??null))
  useEffect(()=>{
    const refresh=(event?:Event)=>{if(!event||(event as CustomEvent<string>).detail===namespace)setPage(previous=>includeReopened(namespace,catalogs.get(namespace)??previous))}
    refresh();window.addEventListener('capstone-session-catalog-changed',refresh)
    return()=>window.removeEventListener('capstone-session-catalog-changed',refresh)
  },[namespace])
  const update:Dispatch<SetStateAction<ThreadListPage|null>>=value=>setPage(previous=>{
    const next=includeReopened(namespace,typeof value==='function'?value(previous):value)
    if(next&&namespace)catalogs.set(namespace,next)
    return next
  })
  return [page,update]
}
