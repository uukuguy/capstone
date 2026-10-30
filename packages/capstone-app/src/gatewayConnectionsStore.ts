import {useEffect,useSyncExternalStore} from 'react'
import type {GatewayConnections,GatewayConnectionInput,GatewayProbe} from './gatewayConnectionTypes'

type Transport={workspaceConnectionsScope?:object;gatewayConnections?:()=>Promise<GatewayConnections>;
  refreshGatewayConnections?:()=>Promise<GatewayConnections>;selectGatewayConnection?:(id:string)=>Promise<GatewayConnections>;
  probeGatewayConnection?:(input:GatewayConnectionInput)=>Promise<GatewayProbe>;addGatewayConnection?:(input:GatewayConnectionInput)=>Promise<GatewayConnections>}
type State={data?:GatewayConnections;loading:boolean;loaded:boolean;error?:string}
const stores=new WeakMap<object,ReturnType<typeof createStore>>()
function createStore(transport:Transport){
  let state:State={loading:false,loaded:false},pending:Promise<void>|undefined,mutating=false,generation=0,supported=true
  let timer:ReturnType<typeof setInterval>|undefined,lastRead=0
  const listeners=new Set<()=>void>()
  const publish=(next:State)=>{state=next;for(const listener of listeners)listener()}
  const message=(error:unknown)=>error instanceof Error?error.message:'网关连接暂未更新。'
  const load=()=>{
    if(pending)return pending
    if(!transport.gatewayConnections||mutating||!supported)return Promise.resolve()
    const current=generation
    lastRead=Date.now()
    if(!state.loaded)publish({...state,loading:true,error:undefined})
    pending=transport.gatewayConnections().then(data=>{
      if(current!==generation)return
      const changed=state.data!==undefined&&state.data.selected_id!==data.selected_id
      publish({data,loading:false,loaded:true})
      if(changed)window.dispatchEvent(new Event('capstone-gateway-changed'))
    }).catch(error=>{
      if(current!==generation)return
      if(error?.status===404){supported=false;publish({loading:false,loaded:true})}
      else publish({...state,loading:false,loaded:true,error:message(error)})
    }).finally(()=>{pending=undefined})
    return pending
  }
  async function update(action:undefined|(()=>Promise<GatewayConnections>),changed=false){
    if(!action)throw new Error('当前服务尚不支持网关管理。')
    if(mutating)throw new Error('网关操作正在进行，请稍后重试。')
    mutating=true;generation++;publish({...state,error:undefined})
    try{
      const data=await action();publish({data,loading:false,loaded:true})
      if(changed)window.dispatchEvent(new Event('capstone-gateway-changed'))
    }catch(error){publish({...state,error:message(error)});throw error}
    finally{mutating=false}
  }
  return {
    snapshot:()=>state,load,
    subscribe:(listener:()=>void)=>{
      listeners.add(listener)
      if(!timer)timer=setInterval(()=>{if(document.visibilityState!=='hidden'&&(state.data?.checking||Date.now()-lastRead>=5000))void load()},1000)
      return()=>{listeners.delete(listener);if(!listeners.size&&timer){clearInterval(timer);timer=undefined}}
    },
    refresh:()=>update(transport.refreshGatewayConnections?.bind(transport)),
    select:(id:string)=>update(transport.selectGatewayConnection?()=>transport.selectGatewayConnection!(id):undefined,true),
    add:(input:GatewayConnectionInput)=>update(transport.addGatewayConnection?()=>transport.addGatewayConnection!(input):undefined),
    probe:(input:GatewayConnectionInput)=>{
      if(!transport.probeGatewayConnection)throw new Error('当前服务尚不支持网关管理。')
      return transport.probeGatewayConnection(input)
    },
  }
}
export function useGatewayConnections(transport:Transport){
  const scope=transport.workspaceConnectionsScope??transport
  let store=stores.get(scope)
  if(!store){store=createStore(transport);stores.set(scope,store)}
  const current=store,state=useSyncExternalStore(current.subscribe,current.snapshot,current.snapshot)
  useEffect(()=>{
    if(!current.snapshot().loaded)void current.load()
    const refresh=()=>{void current.load()}
    window.addEventListener('focus',refresh);window.addEventListener('online',refresh)
    return()=>{window.removeEventListener('focus',refresh);window.removeEventListener('online',refresh)}
  },[current])
  return {...state,refresh:current.refresh,select:current.select,add:current.add,probe:current.probe}
}
