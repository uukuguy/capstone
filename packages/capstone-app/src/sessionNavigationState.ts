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
function durablePinScope(storageKey:string){
  if(!storageKey.startsWith('capstone.thread.'))return storageKey
  const boundary=storageKey.indexOf('.workspace.'),base=boundary<0?storageKey:storageKey.slice(0,boundary)
  return `${base.slice(0,base.lastIndexOf('.'))}${boundary<0?'.workspace.enterprise':storageKey.slice(boundary)}`
}
export function readSessionPins(storageKey='workspace'):string[]|undefined {
  try{
    const scope=durablePinScope(storageKey),key=`capstone.session-pins:${scope}`
    let text=localStorage.getItem(key)
    if(text===null&&scope!==storageKey){
      const recovered=new Set<string>()
      for(let i=0;i<localStorage.length;i++){
        const old=localStorage.key(i)
        if(!old?.startsWith('capstone.session-pins:')||durablePinScope(old.slice('capstone.session-pins:'.length))!==scope)continue
        const value:unknown=JSON.parse(localStorage.getItem(old)??'[]')
        if(!Array.isArray(value)||!value.every(id=>typeof id==='string'))return undefined
        value.forEach(id=>recovered.add(id))
      }
      text=JSON.stringify([...recovered]);localStorage.setItem(key,text)
    }
    const value:unknown=JSON.parse(text??'[]');return Array.isArray(value)&&value.every(id=>typeof id==='string')?value:undefined
  }catch{return undefined}
}
export function useSessionPins(storageKey='workspace'){
  const key=`capstone.session-pins:${durablePinScope(storageKey)}`
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
