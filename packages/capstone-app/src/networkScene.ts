import type {LegacyNetworkView,NetworkDiagram,NetworkLayer} from './types'

export type SceneDetail={label:string;value:string}
type SceneStyle={color?:readonly [number,number,number];state?:'disconnected'|'warning'|'unresolved'}
export type NetworkSceneNode=SceneStyle&{id:string;label:string;kind:string;x?:number|null;y?:number|null;voltageKv?:number|null;sourceRef?:string;details?:readonly SceneDetail[]}
export type NetworkSceneEdge=SceneStyle&{id:string;source:string;target:string;kind:string;label?:string;sourceRef?:string;details?:readonly SceneDetail[];terminalStates?:readonly {nodeId:string;label:string}[]}
export type NetworkScene={ref:string;coordinateSystem:'geographic'|'schematic';nodes:readonly NetworkSceneNode[];edges:readonly NetworkSceneEdge[]}
export type SceneSelection=({type:'node'}&NetworkSceneNode)|({type:'edge'}&NetworkSceneEdge)
export type SceneCamera={x:number;y:number;width:number;height:number}
export type SceneSearchResult={id:string;label:string;kind:string;type:'node'|'edge'}
export type SceneStats={nodes:number;edges:number;indexMs:number;bufferBytes:number;drawnNodes?:number;drawnEdges?:number;limited?:boolean}
export const LARGE_NETWORK_THRESHOLD=1000

/** Electrical geometry keeps its electrical meaning; source topology uses its own adapter. */
export function formalNetworkScene(diagram:NetworkDiagram|LegacyNetworkView,layer?:Pick<NetworkLayer,'overlay'|'annotations'>,historyIds:readonly string[]=[]):NetworkScene {
  const overlay=layer?.overlay,values=new Map(overlay?.values.map(value=>[value.id,value.value]))
  let minimum=Infinity,maximum=-Infinity
  for(const value of values.values()){minimum=Math.min(minimum,value);maximum=Math.max(maximum,value)}
  const states=new Map(layer?.annotations?.states.flatMap(state=>state.ids.map(id=>[id,state] as const)))
  const disconnections=new Map(('disconnections' in diagram?diagram.disconnections:[])?.map(state=>[state.id,state]))
  const historical=new Set(historyIds)
  const regions=layer?.annotations&&layer.annotations.regions.length>1&&layer.annotations.states.some(state=>state.style==='disconnected')?layer.annotations.regions.filter(region=>region.emphasis===true):[]
  const regionById=new Map(regions.flatMap((region,i)=>region.ids.map(id=>[id,{region,index:i}] as const)))
  const regionColors:[[number,number,number],...Array<[number,number,number]>]=[[.46,.35,.65],[.61,.45,.21],[.27,.53,.48],[.69,.39,.44],[.41,.49,.68],[.56,.38,.61]]
  function style(id:string):SceneStyle&{sourceRef?:string;details?:SceneDetail[]}{
    const value=values.get(id),state=states.get(id)?.style||disconnections.get(id)?.style||(disconnections.has(id)?'disconnected':undefined),region=regionById.get(id)
    const details:SceneDetail[]=[...(states.get(id)?[{label:'状态',value:states.get(id)!.label}]:[]),...(region?[{label:'区域',value:region.region.label}]:[])]
    if(value===undefined||!overlay)return {state,color:region?regionColors[region.index%regionColors.length]:historical.has(id)?[.52,.65,.62]:undefined,details}
    const intensity=maximum===minimum?1:(value-minimum)/(maximum-minimum)
    const hue=overlay.metric==='voltage_pu'?178-Math.min(1,Math.abs(value-1)/.15)*160:14-intensity*10
    const saturation=overlay.metric==='voltage_pu'?.65:.68,light=overlay.metric==='voltage_pu'?.39:(54-intensity*16)/100
    const a=saturation*Math.min(light,1-light),channel=(n:number)=>{const k=(n+hue/30)%12;return light-a*Math.max(-1,Math.min(k-3,9-k,1))}
    return {state,color:[channel(0),channel(8),channel(4)],sourceRef:overlay.source_ref,details:[...details,{label:overlay.metric,value:`${value} ${overlay.unit}`}]}
  }
  return {ref:'ref' in diagram?diagram.ref:`${diagram.model.id}:${diagram.model.revision}`,coordinateSystem:'coordinate_system' in diagram?diagram.coordinate_system:'schematic',
    nodes:diagram.buses.map(bus=>({id:bus.id,label:bus.label,kind:'bus',x:bus.x,y:bus.y,voltageKv:'vn_kv' in bus?bus.vn_kv:undefined,...style(bus.id)})),
    edges:diagram.branches.map(branch=>({id:branch.id,label:branch.label,kind:branch.kind,source:branch.from_bus,target:branch.to_bus,...style(branch.id),terminalStates:(states.get(branch.id)?.markers||disconnections.get(branch.id)?.markers)?.map(marker=>({nodeId:marker.bus_id,label:marker.label}))}))}
}
