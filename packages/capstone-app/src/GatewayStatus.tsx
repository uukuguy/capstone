import {useEffect,useRef,useState} from 'react'
import {Check,ChevronUp,Database,Plus,RefreshCw} from 'lucide-react'
import type {GatewayConnectionStatus} from './threadInput'
import type {GatewayConnectionInput,GatewayConnections,GatewayProbe} from './gatewayConnectionTypes'
import './GatewayStatus.css'

type Props={gateway?:GatewayConnectionStatus;notice?:string;onRefresh?:()=>void;connections?:GatewayConnections;onSelect?:(id:string)=>Promise<void>;onRefreshAll?:()=>Promise<void>;onProbe?:(input:GatewayConnectionInput)=>Promise<GatewayProbe>;onAdd?:(input:GatewayConnectionInput)=>Promise<void>}
const statusLabels={unknown:'未检测',checking:'检测中',connected:'可连接',disconnected:'未连通'}
function address(url:string){try{return new URL(url).host}catch{return '地址未知'}}
function checkedTime(value?:string){if(!value)return undefined;const date=new Date(value);return Number.isNaN(date.getTime())?undefined:date.toLocaleString('zh-CN',{hour12:false})}
export default function GatewayStatus({gateway,notice,onRefresh,connections,onSelect,onRefreshAll,onProbe,onAdd}:Props) {
  const root=useRef<HTMLDetailsElement>(null)
  const inspection=useRef<HTMLDetailsElement>(null)
  const [adding,setAdding]=useState(false)
  const [input,setInput]=useState<GatewayConnectionInput>({url:''})
  const [probe,setProbe]=useState<GatewayProbe>()
  const [probing,setProbing]=useState(false)
  const [saving,setSaving]=useState(false)
  const [refreshing,setRefreshing]=useState(false)
  const [selecting,setSelecting]=useState<string>()
  const [inspectedId,setInspectedId]=useState<string>()
  const [error,setError]=useState('')
  const generation=useRef(0)
  const clearForm=()=>{generation.current++;setInput({url:''});setProbe(undefined);setProbing(false);setAdding(false)}
  useEffect(()=>{
    const outside=(event:PointerEvent)=>{if(event.target instanceof Node&&!root.current?.contains(event.target)&&root.current){root.current.open=false;clearForm()}}
    document.addEventListener('pointerdown',outside)
    return()=>document.removeEventListener('pointerdown',outside)
  },[])
  if(!gateway&&!connections)return null
  const selected=connections?.entries.find(entry=>entry.id===connections.selected_id)
  const inspected=connections?.entries.find(entry=>entry.id===inspectedId)??selected
  gateway=connections?(selected?.identity??{available:selected?.status==='connected',...(selected?{endpoint:address(selected.url)}:{})}):gateway!
  const unavailable=connections?selected?.status==='disconnected':!gateway.available
  const label=selected?.identity?.instance_name||selected?.label||gateway.instance_name||gateway.endpoint||gateway.server_name||(gateway.connection_name&&gateway.connection_name.length<=20?gateway.connection_name:undefined)||'数据网关'
  const failure=(cause:unknown,fallback:string)=>{
    const message=cause instanceof Error?cause.message:''
    return message&&message.length<=256&&(!input.token||!message.includes(input.token))&&!/(?:authorization|password|api[_ -]?key|token)\s*[:=]/i.test(message)?message:fallback
  }
  const edit=(field:keyof GatewayConnectionInput,value:string)=>{generation.current++;setInput(previous=>({...previous,[field]:value}));setProbe(undefined);setProbing(false);setError('')}
  const testConnection=async()=>{
    if(!onProbe)return
    try{const url=new URL(input.url);if(!['http:','https:'].includes(url.protocol)||url.username||url.password)throw new Error()}catch{setError('请输入不含账号密码的 HTTP 或 HTTPS 地址');return}
    const version=++generation.current
    setProbing(true);setProbe(undefined);setError('')
    try{const result=await onProbe(input);if(version===generation.current){if(result.identity.available)setProbe(result);else setError('网关当前不可用')}}catch(cause){if(version===generation.current)setError(failure(cause,'连接测试失败，请检查地址与认证信息'))}
    finally{if(version===generation.current)setProbing(false)}
  }
  const save=async()=>{if(!probe||!onAdd||saving)return;setSaving(true);setError('');try{await onAdd(input);clearForm()}catch(cause){setError(failure(cause,'保存失败，请重试'))}finally{setSaving(false)}}
  const refresh=async()=>{if(!onRefreshAll||refreshing)return;setRefreshing(true);setError('');try{await onRefreshAll()}catch(cause){setError(failure(cause,'刷新失败，请重试'))}finally{setRefreshing(false)}}
  const select=async(id:string)=>{if(!onSelect||selecting)return;setSelecting(id);setError('');try{await onSelect(id)}catch(cause){setError(failure(cause,'切换失败'))}finally{setSelecting(undefined)}}
  const detailIdentity=connections?(inspected?.identity??{available:false,endpoint:inspected?address(inspected.url):undefined}):gateway
  const fields=[['实例名称',detailIdentity.instance_name],['配置连接',detailIdentity.connection_name],['环境',detailIdentity.environment_label],['数据源',detailIdentity.data_source_label],['离线模式',typeof detailIdentity.offline==='boolean'?(detailIdentity.offline?'是':'否'):undefined],['MCP 服务',detailIdentity.server_name],['MCP 版本',detailIdentity.server_version],['地址',detailIdentity.endpoint],['检测时间',inspected?.checked_at],['实例标识',detailIdentity.instance_id]]
  const primaryFields=connections?[['环境',detailIdentity.environment_label],['数据源',detailIdentity.data_source_label],['地址',inspected?.url],['检测时间',checkedTime(inspected?.checked_at)]]:fields
  const technicalFields=fields.filter(([name,value])=>Boolean(value)&&['配置连接','MCP 服务','MCP 版本','离线模式','实例标识'].includes(name!))
  const details=<dl><dt>状态</dt><dd>{connections?(inspected?statusLabels[inspected.status]:'未选择'):gateway.available?'可用':'当前不可用'}</dd>
    {primaryFields.filter(([,value])=>Boolean(value)).map(([name,value])=><div className="gateway-status-row" key={name}><dt>{name}</dt><dd>{value}</dd></div>)}
  </dl>
  return <details ref={root} className={`gateway-status${unavailable?' is-unavailable':''}`} onKeyDown={event=>{
    if(event.key==='Escape'&&root.current?.open){event.preventDefault();event.stopPropagation();root.current.open=false;clearForm();root.current.querySelector('summary')?.focus()}
  }} onToggle={()=>{if(root.current&&!root.current.open)clearForm()}}>
    <summary role="button" aria-label={`数据网关：${label}${unavailable?'（当前不可用）':''}`}><Database size={14} aria-hidden="true"/><span>{label==='数据网关'?label:`数据网关 · ${label}`}</span>{unavailable&&<em>当前不可用</em>}<ChevronUp aria-hidden="true"/></summary>
    <div className="gateway-status-panel" aria-label="数据网关连接详情"><header><strong>数据网关</strong>{connections&&onRefreshAll&&<button className="gateway-icon-button" type="button" title="刷新所有网关连接" aria-label="刷新所有网关连接" disabled={refreshing||connections.checking} onClick={()=>void refresh()}><RefreshCw size={15} className={refreshing||connections.checking?'is-spinning':''}/></button>}</header>
    {connections&&<><div className="gateway-connection-list">{connections.entries.map(entry=><button type="button" key={entry.id} className={`gateway-connection${entry.id===inspectedId?' is-inspected':''}`} aria-pressed={entry.id===connections.selected_id} onClick={()=>{setInspectedId(entry.id);if(inspection.current)inspection.current.open=true}}>
      <span className="gateway-connection-copy"><strong>{entry.identity?.instance_name||entry.label}</strong><small>{address(entry.url)}</small></span><span className={`gateway-connection-state is-${entry.status}`}><i aria-hidden="true"/>{selecting===entry.id?'切换中':statusLabels[entry.status]}</span>{entry.id===connections.selected_id&&<Check size={14} aria-label="当前连接"/>}
    </button>)}</div>{!connections.entries.length&&<p>尚未添加网关</p>}
    {onProbe&&onAdd&&!adding&&<button type="button" className="gateway-add-button" disabled={saving} onClick={()=>{setAdding(true);setError('')}}><Plus size={14}/>添加网关</button>}
    {adding&&<form className="gateway-add-form" onSubmit={event=>{event.preventDefault();void testConnection()}}>
      <label>网关 URL<input type="url" autoFocus required value={input.url} disabled={saving} placeholder="https://gateway.example/mcp" onChange={event=>edit('url',event.target.value)}/></label>
      <label>认证令牌（可选）<input type="password" autoComplete="off" value={input.token??''} disabled={saving} onChange={event=>edit('token',event.target.value)}/></label>
      <label>名称（可选）<input value={input.name??''} maxLength={120} disabled={saving} onChange={event=>edit('name',event.target.value)}/></label>
      {probe&&<p role="status">连接成功 · {probe.identity.instance_name||probe.identity.server_name||address(probe.url)}</p>}
      <div className="gateway-form-actions"><button type="submit" disabled={probing||saving||!input.url}>{probing?'测试中…':'测试连接'}</button><button type="button" disabled={!probe||saving} onClick={()=>void save()}>{saving?'保存中…':'保存网关'}</button><button type="button" disabled={saving} onClick={clearForm}>取消</button></div>
    </form>}</>}
    {error&&<p role="alert">{error}</p>}
    {connections?<details ref={inspection} className="gateway-instance-details" key={inspectedId??'initial'} open={inspectedId!==undefined}><summary>实例详情</summary>
      {inspected&&<div className="gateway-inspector-heading"><strong>{inspected.identity?.instance_name||inspected.label}</strong><button className="gateway-use-button" type="button" disabled={!onSelect||Boolean(selecting)||inspected.id===connections.selected_id} onClick={()=>void select(inspected.id)}>{inspected.id===connections.selected_id?'当前使用':selecting===inspected.id?'切换中…':'使用此网关'}</button></div>}
      {details}
      {technicalFields.length>0&&<details className="gateway-technical-details"><summary>更多连接信息</summary><dl>{technicalFields.map(([name,value])=><div className="gateway-status-row" key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl></details>}
    </details>:details}
    {notice&&notice!==error&&<p role="status">{notice}</p>}{!connections&&onRefresh&&<button type="button" onClick={onRefresh}>刷新连接信息</button>}</div>
  </details>
}
