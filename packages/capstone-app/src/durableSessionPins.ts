export type PinDocument={schema:'capstone-session-pins/1';workspace:string;revision:number;pins:string[]}
export type PinPort={read:()=>Promise<unknown>;write:(operation:{thread_id:string;pinned:boolean}|{import:string[]})=>Promise<unknown>}
export function parsePinState(value:unknown,workspace:string):PinDocument{
  const item=value as Partial<PinDocument>|null
  if(!item||item.schema!=='capstone-session-pins/1'||item.workspace!==workspace||typeof item.revision!=='number'||!Number.isSafeInteger(item.revision)||item.revision<0||!Array.isArray(item.pins)||!item.pins.every(id=>typeof id==='string'&&id.length>0)||new Set(item.pins).size!==item.pins.length)throw new Error('置顶状态响应无效')
  return item as PinDocument
}
export class PinState{
  snapshot:{pins:string[];revision:number;ready:boolean;error:string}={pins:[],revision:-1,ready:false,error:''}
  private listeners=new Set<()=>void>()
  private queue:Promise<void>=Promise.resolve()
  constructor(readonly workspace:string,private port:PinPort){}
  setPort(port:PinPort){this.port=port}
  subscribe=(listener:()=>void)=>{this.listeners.add(listener);return()=>{this.listeners.delete(listener)}}
  private emit(){this.listeners.forEach(listener=>listener())}
  private accept(value:unknown){const item=parsePinState(value,this.workspace);if(item.revision>=this.snapshot.revision){this.snapshot={pins:item.pins,revision:item.revision,ready:true,error:''};this.emit()}}
  async refresh(){try{this.accept(await this.port.read())}catch{this.snapshot={...this.snapshot,error:'置顶状态暂时无法读取，已保留上次记录。'};this.emit()}}
  async import(ids:string[]){try{for(let offset=0;offset<ids.length;offset+=1000)this.accept(await this.port.write({import:ids.slice(offset,offset+1000)}));await this.refresh()}catch{this.snapshot={...this.snapshot,error:'原置顶记录尚未同步，请重试。'};this.emit()}}
  toggle(id:string){this.queue=this.queue.then(async()=>{if(!this.snapshot.ready){await this.refresh();if(!this.snapshot.ready)return}try{this.accept(await this.port.write({thread_id:id,pinned:!this.snapshot.pins.includes(id)}))}catch{this.snapshot={...this.snapshot,error:'置顶变更未保存，请重试。'};this.emit()}});return this.queue}
}
const states=new Map<string,PinState>()
export function registerSessionPins(key:string,workspace:string,port:PinPort){const state=states.get(key);if(state)state.setPort(port);else states.set(key,new PinState(workspace,port))}
export function durableSessionPins(key:string){return states.get(key)}
