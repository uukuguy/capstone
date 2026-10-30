import type {GatewayConnectionStatus} from './threadInput'

export type GatewayConnectionInput = {url:string;token?:string;name?:string}
export type GatewayProbe = {url:string;identity:GatewayConnectionStatus}
export type GatewayConnectionEntry = {
  id:string;label:string;url:string
  status:'unknown'|'checking'|'connected'|'disconnected'
  checked_at?:string;identity?:GatewayConnectionStatus;error?:string
}
export type GatewayConnections = {
  schema:'capstone-gateway-connections/1';revision:number
  selected_id?:string;entries:GatewayConnectionEntry[];checking:boolean
}
