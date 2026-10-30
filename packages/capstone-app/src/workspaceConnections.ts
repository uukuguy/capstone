import {useEffect,useSyncExternalStore} from 'react'
import type {GatewayConnectionStatus} from './threadInput'

export type WorkspaceConnections={schema:'capstone-workspace-connections/1';data_gateway?:GatewayConnectionStatus}
type Transport={workspaceConnectionsScope?:object;workspaceConnections?:()=>Promise<WorkspaceConnections>}
type State={data?:WorkspaceConnections;loading:boolean;error?:string;loaded:boolean}
const stores=new WeakMap<object,ReturnType<typeof createStore>>()
function createStore(transport:Transport){
  let state:State={loading:false,loaded:false}
  let pending:Promise<void>|undefined
  const listeners=new Set<()=>void>()
  const publish=(next:State)=>{state=next;listeners.forEach(listener=>listener())}
  return {
    snapshot:()=>state,
    subscribe:(listener:()=>void)=>{listeners.add(listener);return()=>{listeners.delete(listener)}},
    load:()=>{
      if(pending)return pending
      if(!transport.workspaceConnections)return Promise.resolve()
      publish({...state,loading:true,error:undefined})
      pending=transport.workspaceConnections().then(data=>publish({data,loading:false,loaded:true})).catch(error=>{
        if(error?.status===404)publish({loading:false,loaded:true})
        else publish({...state,loading:false,loaded:true,error:'网关连接信息暂未更新。'})
      }).finally(()=>{pending=undefined})
      return pending
    },
  }
}
export function useWorkspaceConnections(transport:Transport){
  const scope=transport.workspaceConnectionsScope??transport
  let store=stores.get(scope)
  if(!store){store=createStore(transport);stores.set(scope,store)}
  const current=store
  const state=useSyncExternalStore(current.subscribe,current.snapshot,current.snapshot)
  useEffect(()=>{
    if(!current.snapshot().loaded)void current.load()
    const refresh=()=>{void current.load()}
    window.addEventListener('focus',refresh);window.addEventListener('online',refresh);window.addEventListener('capstone-gateway-changed',refresh)
    return()=>{window.removeEventListener('focus',refresh);window.removeEventListener('online',refresh);window.removeEventListener('capstone-gateway-changed',refresh)}
  },[current])
  return {...state,refresh:current.load}
}
