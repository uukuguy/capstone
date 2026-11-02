export type NetworkSymbol={code:number;label:string;path:string;discard:string}
const symbol=(code:number,label:string,path:string,discard:string):NetworkSymbol=>({code,label,path,discard})
export const sceneGlyphs={
  node:symbol(0,'连接节点','M 10 7 A 3 3 0 1 0 10 13 A 3 3 0 1 0 10 7','d>0.8'),
  bus:symbol(1,'电气母线','M 2 10 H 18','abs(p.x)>0.9||abs(p.y)>0.13'),
  transformer:symbol(2,'变压器','M 7 5 A 5 5 0 1 0 7 15 A 5 5 0 1 0 7 5 M 13 5 A 5 5 0 1 0 13 15 A 5 5 0 1 0 13 5','min(abs(length(p-vec2(-0.3,0.0))-0.45),abs(length(p-vec2(0.3,0.0))-0.45))>0.13'),
  disconnector:symbol(3,'隔离开关','M 10 2 L 18 10 L 10 18 L 2 10 Z M 4 10 H 16','abs(abs(p.x)+abs(p.y)-0.8)>0.12&&abs(p.y)>0.10'),
  station:symbol(4,'站点分组','M 3 3 H 17 V 17 H 3 Z','max(abs(p.x),abs(p.y))>0.8||max(abs(p.x),abs(p.y))<0.52'),
  boundary:symbol(5,'视图边界','M 10 1 L 19 10 L 10 19 L 1 10 Z','abs(abs(p.x)+abs(p.y)-0.9)>0.12'),
  winding:symbol(6,'绕组','M 10 4 A 6 6 0 1 0 10 16 A 6 6 0 1 0 10 4','abs(d-0.62)>0.14'),
  breaker:symbol(7,'断路器','M 3 3 H 17 V 17 H 3 Z M 5 5 L 15 15 M 15 5 L 5 15','max(abs(p.x),abs(p.y))>0.8||(max(abs(p.x),abs(p.y))<0.55&&min(abs(p.x-p.y),abs(p.x+p.y))>0.13)'),
  ground:symbol(8,'接地隔离开关','M 10 1 L 16 6 L 10 11 L 4 6 Z M 10 11 V 15 M 4 15 H 16 M 6 18 H 14','!(abs(abs(p.x)+abs(p.y+0.35)-0.5)<0.12||abs(p.x)<0.10&&p.y>0.05&&p.y<0.6||abs(p.y-0.55)<0.10&&abs(p.x)<0.65||abs(p.y-0.85)<0.10&&abs(p.x)<0.4)'),
  voltage:symbol(9,'电压层级分组','M 3 3 H 17 V 17 H 3 Z M 6 7 H 14 M 6 13 H 14','max(abs(p.x),abs(p.y))>0.8||(max(abs(p.x),abs(p.y))<0.55&&!(abs(abs(p.y)-0.3)<0.10&&abs(p.x)<0.45))'),
  terminal:symbol(10,'端子','M 10 3 V 10 M 10 10 A 3 3 0 1 0 10 16 A 3 3 0 1 0 10 10','!(length(p-vec2(0.0,0.3))<0.3||abs(p.x)<0.1&&p.y<0.3&&p.y> -0.8)'),
  boundaryHalo:symbol(11,'视图边界','M 10 1 L 19 10 L 10 19 L 1 10 Z','abs(abs(p.x)+abs(p.y)-0.9)>0.08'),
  disconnected:symbol(12,'已记录断开标记','M 3 3 L 17 17 M 17 3 L 3 17','min(abs(p.x-p.y),abs(p.x+p.y))>0.13'),
  unresolved:symbol(13,'状态未核验','M 10 3 A 7 7 0 1 0 10 17 A 7 7 0 1 0 10 3 M 10 9 V 11','abs(d-0.7)>0.12&&d>0.13'),
  line:symbol(14,'源线路记录','M 2 7 H 18 M 2 13 H 18','abs(p.x)>0.9||abs(abs(p.y)-0.3)>0.12'),
  switchUnknown:symbol(15,'开关状态未知','M 2 10 H 6 M 14 10 H 18 M 7 7 H 13 M 10 4 V 6','abs(p.x)>0.9||abs(abs(p.x)-0.5)<0.10&&abs(p.y)>0.25||abs(abs(p.y)-0.3)<0.1&&abs(p.x)>0.15'),
  disconnectorUnknown:symbol(16,'隔离开关 · 状态未知','M 2 10 H 6 M 14 10 H 18 M 5 8 A 2 2 0 1 0 5 12 A 2 2 0 1 0 5 8 M 15 8 A 2 2 0 1 0 15 12 A 2 2 0 1 0 15 8','abs(p.x)>0.9||abs(abs(p.x)-0.5)<0.16||abs(p.y)>0.3'),
  breakerUnknown:symbol(17,'断路器 · 状态未知','M 3 3 H 17 V 17 H 3 Z M 8 10 H 12 M 10 8 V 12','max(abs(p.x),abs(p.y))>0.8||abs(p.x)>0.18&&abs(p.y)>0.18'),
  groundUnknown:symbol(18,'接地隔离开关 · 状态未知','M 2 7 H 6 M 14 7 H 18 M 7 5 A 3 3 0 1 0 7 9 A 3 3 0 1 0 7 5 M 10 11 V 14 M 5 14 H 15','abs(p.x)>0.9||abs(abs(p.x)-0.5)<0.18&&abs(p.y)>0.1||abs(p.y)>0.9||abs(p.y-0.4)<0.12&&abs(p.x)>0.5'),
  switchOpen:symbol(19,'开关 · 分位（显式）','M 2 10 H 7 M 13 10 H 18 M 7 10 L 13 5','abs(p.x)>0.9||abs(p.y)>0.9||abs(p.x)<0.25&&abs(p.y)>0.1'),
  switchClosed:symbol(20,'开关 · 合位（显式）','M 2 10 H 18 M 7 6 V 14 M 13 6 V 14','abs(p.x)>0.9||abs(p.y)>0.9||abs(abs(p.x)-0.3)>0.1&&abs(p.y)>0.2'),
  generator:symbol(21,'发电机','M 10 3 A 7 7 0 1 0 10 17 A 7 7 0 1 0 10 3 M 6 11 Q 8 7 10 11 T 14 11','abs(d-0.7)>0.12&&!(abs(p.y)<0.2&&abs(p.x)<0.35)'),
  load:symbol(22,'负荷','M 10 2 L 17 16 H 3 Z M 7 12 H 13','max(abs(p.x),abs(p.y))>0.85||abs(p.y+0.2)<0.10&&abs(p.x)>0.15&&abs(p.x)<0.55'),
  transformer3w:symbol(23,'三绕组变压器','M 7 4 A 4 4 0 1 0 7 12 A 4 4 0 1 0 7 4 M 13 4 A 4 4 0 1 0 13 12 A 4 4 0 1 0 13 4 M 10 11 A 4 4 0 1 0 10 19 A 4 4 0 1 0 10 11','min(abs(length(p-vec2(-0.3,-0.25))-0.38),min(abs(length(p-vec2(0.3,-0.25))-0.38),abs(length(p-vec2(0.0,0.38))-0.38)))>0.12'),
} as const
const kinds:Record<string,NetworkSymbol>={bus:sceneGlyphs.bus,busbars:{...sceneGlyphs.bus,label:'母线条（源记录）'},transformer:sceneGlyphs.transformer,transformers:sceneGlyphs.transformer,trafo:sceneGlyphs.transformer,trafo3w:sceneGlyphs.transformer3w,station:sceneGlyphs.station,voltage_group:sceneGlyphs.voltage,voltage_level:sceneGlyphs.voltage,switch:sceneGlyphs.switchUnknown,disconnectors:sceneGlyphs.disconnectorUnknown,ground_disconnectors:sceneGlyphs.groundUnknown,breakers:sceneGlyphs.breakerUnknown,windings:sceneGlyphs.winding,terminal:sceneGlyphs.terminal,connection_node:sceneGlyphs.node,source_node:sceneGlyphs.node,boundary:sceneGlyphs.boundary,line:sceneGlyphs.line,generator:sceneGlyphs.generator,generators:sceneGlyphs.generator,load:sceneGlyphs.load,loads:sceneGlyphs.load}
export function networkSymbol(kind:string,switchState:'open'|'closed'|'unknown'='unknown'):NetworkSymbol{
  if(kind==='port')return {...sceneGlyphs.terminal,label:'端口'}
  const aliases:Record<string,string>={busbar:'busbars',busbar_section:'busbars',breaker:'breakers',disconnector:'disconnectors',ground_disconnector:'ground_disconnectors',winding:'windings'}
  kind=aliases[kind]||kind
  const base=kinds[kind]
  if(!base)return {...sceneGlyphs.node,label:`源对象 · ${kind}`}
  if(!['switch','breakers','disconnectors','ground_disconnectors'].includes(kind)||switchState==='unknown')return base
  const stateGlyph=switchState==='open'?sceneGlyphs.switchOpen:sceneGlyphs.switchClosed
  const equipment:Record<string,string>={switch:'开关',breakers:'断路器',disconnectors:'隔离开关',ground_disconnectors:'接地隔离开关'}
  return {...stateGlyph,label:`${equipment[kind]} · ${switchState==='open'?'分位':'合位'}（显式）`}
}
/** Same predicates and code registry as the HTML legend; no inferred switch position. */
export const NETWORK_GLYPH_FRAGMENT=Object.values(sceneGlyphs).map((glyph,i)=>`${i?'else ':''}if(symbol<${(glyph.code+.5).toFixed(1)}){if(${glyph.discard})discard;}`).join('')
