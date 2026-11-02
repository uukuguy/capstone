import GatewayStatus from './GatewayStatus'
import {useMemo} from 'react'
import {useWorkspaceConnections} from './workspaceConnections'
import {useGatewayConnections} from './gatewayConnectionsStore'
import type {HttpThreadTransport} from './threadHttpTransport'
import './WorkspaceConnectionStatus.css'

export function WorkspaceGatewayStatus({transport,threadId,locked=false}:{transport:HttpThreadTransport;threadId?:string;locked?:boolean}){
  const connection=useWorkspaceConnections(transport)
  const scoped=useMemo(()=>!threadId?transport:{
    workspaceConnectionsScope:{},
    gatewayConnections:()=>transport.threadGatewayConnections(threadId),
    selectGatewayConnection:(id:string)=>transport.selectThreadGatewayConnection(threadId,id),
    refreshGatewayContract:()=>transport.refreshThreadGatewayContract(threadId),
    refreshGatewayConnections:async()=>{await transport.refreshGatewayConnections();return transport.threadGatewayConnections(threadId)},
    probeGatewayConnection:transport.probeGatewayConnection.bind(transport),addGatewayConnection:transport.addGatewayConnection.bind(transport),
  },[transport,threadId])
  const instances=useGatewayConnections(scoped)
  return <div className="workspace-connections-slot" aria-label="工作台数据网关">
    {instances.data||(!threadId&&connection.data?.data_gateway)?<GatewayStatus gateway={threadId?undefined:connection.data?.data_gateway} connections={instances.data?{...instances.data,locked:locked||instances.data.locked}:undefined} notice={instances.error||(!threadId?connection.error:undefined)}
      onSelect={instances.select} onRefreshAll={instances.refresh} onRefreshContract={instances.refreshContract} onProbe={instances.probe} onAdd={instances.add}
      onRefresh={instances.data?undefined:()=>void connection.refresh()}/>:instances.error?<span role="status">{instances.error}</span>:instances.loading?<span>读取会话网关信息…</span>:null}
  </div>
}

export function SessionConnectionStatus({state,error,pending=false,recovering=false}:{state:string;error?:string;pending?:boolean;recovering?:boolean}){
  if(state==='live'&&!pending&&!error)return null
  return <div className="workspace-session-connection-slot">{(state!=='live'||pending||!!error)&&<details className="workspace-connection-status" aria-label="会话连接状态">
    <summary><i aria-hidden="true"/>{pending?'操作待确认':state==='live'&&error?'状态同步异常':error?(recovering?'连接恢复中':'连接待确认'):'连接中'}</summary>
    <div>{pending?<p>上次操作结果待确认；重试将使用同一请求。</p>:null}{error?<p>{error}</p>:state!=='live'?<p>正在恢复会话实时连接，后台执行状态待确认。</p>:null}</div>
  </details>}</div>
}
