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
} as const
const kinds:Record<string,NetworkSymbol>={bus:sceneGlyphs.bus,busbars:{...sceneGlyphs.bus,label:'母线条（源记录）'},transformer:sceneGlyphs.transformer,transformers:sceneGlyphs.transformer,trafo:sceneGlyphs.transformer,trafo3w:sceneGlyphs.transformer,station:sceneGlyphs.station,voltage_group:sceneGlyphs.voltage,voltage_level:sceneGlyphs.voltage,switch:sceneGlyphs.disconnector,disconnectors:sceneGlyphs.disconnector,ground_disconnectors:sceneGlyphs.ground,breakers:sceneGlyphs.breaker,windings:sceneGlyphs.winding,terminal:sceneGlyphs.terminal,connection_node:sceneGlyphs.node,source_node:sceneGlyphs.node,boundary:sceneGlyphs.boundary,line:sceneGlyphs.line}
export function networkSymbol(kind:string):NetworkSymbol{return kinds[kind]||{...sceneGlyphs.node,label:`源对象 · ${kind}`}}
/** Same predicates and code registry as the HTML legend; no inferred switch position. */
export const NETWORK_GLYPH_FRAGMENT=Object.values(sceneGlyphs).map((glyph,i)=>`${i?'else ':''}if(symbol<${(glyph.code+.5).toFixed(1)}){if(${glyph.discard})discard;}`).join('')
