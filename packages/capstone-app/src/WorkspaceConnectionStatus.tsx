import GatewayStatus from './GatewayStatus'
import {useWorkspaceConnections} from './workspaceConnections'
import type {HttpThreadTransport} from './threadHttpTransport'
import './WorkspaceConnectionStatus.css'

export function WorkspaceGatewayStatus({transport}:{transport:HttpThreadTransport}){
  const connection=useWorkspaceConnections(transport)
  return <div className="workspace-connections-slot" aria-label="工作台数据网关">
    {connection.data?.data_gateway?<GatewayStatus gateway={connection.data.data_gateway} notice={connection.error} onRefresh={()=>void connection.refresh()}/>:connection.error?<details className="workspace-connection-status"><summary>网关信息待确认</summary><div>{connection.error}<button type="button" onClick={()=>void connection.refresh()}>重试读取</button></div></details>:connection.loading?<span>读取网关信息…</span>:null}
  </div>
}

export function SessionConnectionStatus({state,error,pending=false,recovering=false}:{state:string;error?:string;pending?:boolean;recovering?:boolean}){
  return <details className="workspace-connection-status" aria-label="会话连接状态">
    <summary><i aria-hidden="true" className={state==='live'?'is-live':''}/>{pending?'操作待确认':state==='live'?'已连接':error?(recovering?'连接恢复中':'连接待确认'):'连接中'}</summary>
    <div>{pending?<p>上次操作结果待确认；重试将使用同一请求。</p>:null}<p>{error||(state==='live'?'会话实时连接正常。':'正在恢复会话实时连接，后台执行状态待确认。')}</p></div>
  </details>
}
