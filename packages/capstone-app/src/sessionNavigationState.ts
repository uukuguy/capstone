import {useEffect,useState} from 'react'
import type {ThreadDescriptor} from './threadManagement'
import {sessionTypeNames} from './SessionEntry'
import {displaySessionTitle} from './sessionTitle'
import {currentWorkspaceName} from './workspaceName'
export type SessionNavItem=Pick<ThreadDescriptor,'threadId'|'modelId'|'sessionTitle'|'sessionType'>&Partial<ThreadDescriptor>
export function sessionName(item:SessionNavItem):string{return item.sessionTitle&&displaySessionTitle(item.sessionTitle)||item.sessionType&&sessionTypeNames[item.sessionType]||(item.modelId?'电网分析与决策':'工作会话')}
export function navigateSession(id:string){
  const url=new URL(window.location.href)
  if(url.searchParams.get('thread')===id&&url.searchParams.get('workspace')===currentWorkspaceName())return
  url.searchParams.set('workspace',currentWorkspaceName());url.searchParams.set('thread',id);url.searchParams.delete('thread-fixture')
  window.history.pushState({},'',url);window.dispatchEvent(new PopStateEvent('popstate'))
}
export function readSessionPins(storageKey='workspace'):string[]|undefined {
  try{const value:unknown=JSON.parse(localStorage.getItem(`capstone.session-pins:${storageKey}`)??'[]');return Array.isArray(value)&&value.every(id=>typeof id==='string')?value:undefined}catch{return undefined}
}
export function useSessionPins(storageKey='workspace'){
  const key=`capstone.session-pins:${storageKey}`
  const read=()=>readSessionPins(storageKey)??[]
  const [pins,setPins]=useState(read)
  useEffect(()=>{
    const refresh=()=>setPins(read())
    // Hidden Activity views stop listening. Read durable preferences on every reveal.
    refresh()
    const storage=(event:StorageEvent)=>{if(event.key===key||event.key===null)refresh()}
    window.addEventListener('capstone-session-pins',refresh)
    window.addEventListener('storage',storage)
    return()=>{window.removeEventListener('capstone-session-pins',refresh);window.removeEventListener('storage',storage)}
  },[key])
  const toggle=(id:string)=>{const current=read(),next=current.includes(id)?current.filter(value=>value!==id):[...current,id];try{localStorage.setItem(key,JSON.stringify(next))}catch{/* Retain live state. */}setPins(next);window.dispatchEvent(new Event('capstone-session-pins'))}
  return {pins,toggle}
}
export function orderSessions(items:readonly SessionNavItem[],pins:readonly string[]){return [...items.filter(item=>pins.includes(item.threadId)),...items.filter(item=>!pins.includes(item.threadId))]}
