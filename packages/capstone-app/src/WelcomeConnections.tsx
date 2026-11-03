import {Database, Server} from 'lucide-react'
import type {InputCatalog,GatewayConnectionStatus} from './threadInput'
import './WelcomeConnections.css'

function gatewayAddress(value?:string){
  if(!value)return undefined
  try{return new URL(value.includes('://')?value:`http://${value}`).host||undefined}catch{return undefined}
}

/** Read the same catalog and selected draft as the composer; never probe here. */
export default function WelcomeConnections({catalog,gateway,profileId,loading=false}:{catalog?:InputCatalog;gateway?:GatewayConnectionStatus;profileId?:string;loading?:boolean}){
  const profile=catalog?.llm_profiles?.profiles.find(item=>item.id===(profileId??catalog.llm_profiles?.default_profile_id))
  const address=gatewayAddress(gateway?.endpoint)
  const gatewayName=gateway?.instance_name||gateway?.environment_label||gateway?.connection_name||gateway?.server_name
  return <section className="welcome-connections" aria-label="当前会话连接">
    <div className="welcome-connection-card">
      <div className="welcome-connection-heading"><Database aria-hidden="true"/><span>数据网关</span><span className="welcome-connection-state" data-state={gateway?.available?'available':'unknown'}>{loading&&!gateway?'读取中':gateway?gateway.available?'可用':'待确认':'尚未取得'}</span></div>
      <strong>{gatewayName||address||(loading?'正在读取网关信息…':'尚未提供实例信息')}</strong>
      <span className="welcome-connection-detail">{address&&address!==gatewayName?address:gateway?.data_source_label||'当前会话使用的数据服务'}</span>
    </div>
    <div className="welcome-connection-card">
      <div className="welcome-connection-heading"><Server aria-hidden="true"/><span>LLM</span><span className="welcome-connection-state" data-state={profile?.available?'available':'unknown'}>{loading&&!profile?'读取中':profile?profile.available?'已选择':'不可用':'尚未取得'}</span></div>
      <strong>{profile?.model||profile?.label||(loading?'正在读取模型信息…':'尚未提供模型信息')}</strong>
      <span className="welcome-connection-detail">{profile?.label&&profile.label!==profile.model?profile.label:'当前指令使用的语言模型'}</span>
    </div>
  </section>
}
