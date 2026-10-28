import {useEffect,useRef} from 'react'
import {ChevronDown,Network} from 'lucide-react'
import type {GatewayConnectionStatus} from './threadInput'
import './GatewayStatus.css'

export default function GatewayStatus({gateway}:{gateway?:GatewayConnectionStatus}) {
  const root=useRef<HTMLDetailsElement>(null)
  useEffect(()=>{
    const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target)&&root.current)root.current.open=false}
    document.addEventListener('pointerdown',outside)
    return()=>document.removeEventListener('pointerdown',outside)
  },[])
  if(!gateway)return null
  const label=gateway.instance_name||gateway.connection_name||gateway.endpoint||gateway.server_name||'数据网关'
  const fields=[['实例名称',gateway.instance_name],['配置连接',gateway.connection_name],['环境',gateway.environment_label],['数据源',gateway.data_source_label],['离线模式',typeof gateway.offline==='boolean'?(gateway.offline?'是':'否'):undefined],['MCP 服务',gateway.server_name],['MCP 版本',gateway.server_version],['地址',gateway.endpoint],['实例标识',gateway.instance_id]]
  return <details ref={root} className={`gateway-status${gateway.available?'':' is-unavailable'}`} onKeyDown={event=>{
    if(event.key==='Escape'&&root.current?.open){event.preventDefault();event.stopPropagation();root.current.open=false;root.current.querySelector('summary')?.focus()}
  }}>
    <summary role="button" aria-label={`数据网关：${label}${gateway.available?'':'（当前不可用）'}`}><Network aria-hidden="true"/><span>{label}</span>{!gateway.available&&<em>当前不可用</em>}<ChevronDown aria-hidden="true"/></summary>
    <div className="gateway-status-panel" aria-label="数据网关连接详情"><strong>数据网关</strong><dl><dt>状态</dt><dd>{gateway.available?'可用':'当前不可用'}</dd>
      {fields.filter(([,value])=>Boolean(value)).map(([name,value])=><div className="gateway-status-row" key={name}><dt>{name}</dt><dd>{value}</dd></div>)}
    </dl></div>
  </details>
}
