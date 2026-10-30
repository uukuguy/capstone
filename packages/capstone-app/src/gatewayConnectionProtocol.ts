import {parseGatewayConnectionStatus} from './threadInput'
import type {GatewayConnections,GatewayConnectionEntry,GatewayProbe} from './gatewayConnectionTypes'

const record=(value:unknown):Record<string,unknown>=>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('网关连接信息无效');return value as Record<string,unknown>}
const text=(value:unknown)=>{if(typeof value!=='string'||!value||value.length>2048||/[\u0000-\u001f\u007f]/.test(value))throw new Error('网关连接信息无效');return value}
function address(value:unknown){
  const raw=text(value),url=new URL(raw)
  if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search||url.hash)throw new Error('网关地址无效')
  return raw
}
export function parseGatewayConnections(value:unknown):GatewayConnections{
  const item=record(value)
  if(item.schema!=='capstone-gateway-connections/1'||!Number.isSafeInteger(item.revision)||Number(item.revision)<0||typeof item.checking!=='boolean'||!Array.isArray(item.entries))throw new Error('网关连接信息无效')
  const entries:GatewayConnectionEntry[]=item.entries.map(value=>{
    const row=record(value)
    if(!['unknown','checking','connected','disconnected'].includes(String(row.status)))throw new Error('网关状态无效')
    return {id:text(row.id),label:text(row.label),url:address(row.url),status:row.status as GatewayConnectionEntry['status'],
      ...(row.checked_at===undefined?{}:{checked_at:text(row.checked_at)}),...(row.error===undefined?{}:{error:text(row.error)}),
      ...(row.identity===undefined?{}:{identity:parseGatewayConnectionStatus(row.identity)})}
  })
  if(new Set(entries.map(entry=>entry.id)).size!==entries.length)throw new Error('网关实例重复')
  const selected=item.selected_id===undefined?undefined:text(item.selected_id)
  if(selected&&!entries.some(entry=>entry.id===selected))throw new Error('所选网关不存在')
  return {schema:'capstone-gateway-connections/1',revision:Number(item.revision),entries,checking:item.checking,...(selected?{selected_id:selected}:{})}
}
export function parseGatewayProbe(value:unknown):GatewayProbe{
  const item=record(value)
  return {url:address(item.url),identity:parseGatewayConnectionStatus(item.identity)}
}
