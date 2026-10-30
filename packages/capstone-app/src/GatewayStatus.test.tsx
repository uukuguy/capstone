import {afterEach,expect,it,vi} from 'vitest'
import '@testing-library/jest-dom/vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import GatewayStatus from './GatewayStatus'
import {parseInputCatalog} from './threadInput'

afterEach(cleanup)

const connections={schema:'capstone-gateway-connections/1' as const,revision:1,selected_id:'a',checking:false,entries:[{id:'a',label:'当前实例',url:'http://one.test:8000/mcp',status:'connected' as const},{id:'b',label:'另一个实例',url:'https://two.test/mcp',status:'unknown' as const}]}
it('shows the actionable backend failure once without replacing it with a generic error',async()=>{
  const message='有任务正在执行，请结束后切换网关。'
  render(<GatewayStatus connections={connections} notice={message} onSelect={async()=>{throw new Error(message)}}/>)
  fireEvent.click(screen.getByRole('button',{name:/数据网关：/}))
  fireEvent.click(screen.getByRole('button',{name:/另一个实例/}))
  fireEvent.click(screen.getByRole('button',{name:'使用此网关'}))
  expect(await screen.findByRole('alert')).toHaveTextContent(message)
  expect(screen.getAllByText(message)).toHaveLength(1)
})
it('collapses current details and never borrows a previous gateway identity',()=>{
  render(<GatewayStatus connections={{...connections,selected_id:'b',entries:[{...connections.entries[1],status:'disconnected'}]}} gateway={{available:true,instance_name:'旧实例',server_name:'旧服务'}} onRefresh={vi.fn()} onRefreshAll={vi.fn()}/>)
  fireEvent.click(screen.getByRole('button',{name:'数据网关：另一个实例（当前不可用）'}))
  expect(screen.queryByText('旧实例')).toBeNull()
  expect(screen.queryByText('旧服务')).toBeNull()
  expect(screen.queryByRole('button',{name:'刷新连接信息'})).toBeNull()
  const details=screen.getByText('实例详情').closest('details')!
  expect(details.open).toBe(false)
  fireEvent.click(screen.getByText('实例详情'))
  expect(details.open).toBe(true)
  expect(screen.getAllByText('未连通').length).toBe(2)
  expect(screen.getByText('https://two.test/mcp')).toBeTruthy()
})
it('refreshes asynchronously and preserves selection when switching fails',async()=>{
  const select=vi.fn().mockRejectedValue(new Error('切换失败'))
  let finish!:()=>void
  const refresh=vi.fn(()=>new Promise<void>(resolve=>{finish=resolve}))
  const checkedAt='2026-10-30T18:00:00Z'
  render(<GatewayStatus connections={{...connections,entries:connections.entries.map(entry=>entry.id==='b'?{...entry,checked_at:checkedAt,identity:{available:true,endpoint:'host.docker.internal:8000',server_version:'1.2.3'}}:entry)}} onSelect={select} onRefreshAll={refresh}/>)
  fireEvent.click(screen.getByRole('button',{name:/数据网关：/}))
  fireEvent.click(screen.getByRole('button',{name:'刷新所有网关连接'}))
  expect(screen.getByRole('button',{name:'刷新所有网关连接'})).toBeDisabled()
  finish()
  await waitFor(()=>expect(screen.getByRole('button',{name:'刷新所有网关连接'})).not.toBeDisabled())
  fireEvent.click(screen.getByRole('button',{name:/另一个实例/}))
  expect(select).not.toHaveBeenCalled()
  expect(screen.getByText('实例详情').closest('details')?.open).toBe(true)
  expect(screen.getByRole('button',{name:'数据网关：当前实例'})).toBeTruthy()
  expect(screen.getByRole('button',{name:/另一个实例/})).toHaveClass('is-inspected')
  expect(screen.getByText('https://two.test/mcp')).toBeTruthy()
  expect(screen.queryByText('host.docker.internal:8000')).toBeNull()
  expect(screen.getByText(new Date(checkedAt).toLocaleString('zh-CN',{hour12:false}))).toBeTruthy()
  expect(screen.getByText('更多连接信息').closest('details')?.open).toBe(false)
  fireEvent.click(screen.getByRole('button',{name:'使用此网关'}))
  await screen.findByText('切换失败')
  expect(select).toHaveBeenCalledWith('b')
  expect(screen.getByRole('button',{name:/当前实例.*当前连接/})).toHaveAttribute('aria-pressed','true')
})
it('requires a fresh successful probe after editing and clears the token after save',async()=>{
  const probe=vi.fn().mockResolvedValue({url:'https://new.test/mcp',identity:{available:true,instance_name:'探测实例'}})
  const add=vi.fn().mockResolvedValue(undefined)
  render(<GatewayStatus connections={connections} onProbe={probe} onAdd={add}/>)
  fireEvent.click(screen.getByRole('button',{name:/数据网关：/}))
  fireEvent.click(screen.getByRole('button',{name:'添加网关'}))
  fireEvent.change(screen.getByLabelText('网关 URL'),{target:{value:'https://new.test/mcp'}})
  fireEvent.change(screen.getByLabelText('认证令牌（可选）'),{target:{value:'private-token'}})
  fireEvent.click(screen.getByRole('button',{name:'测试连接'}))
  await screen.findByText('连接成功 · 探测实例')
  expect(screen.getByRole('button',{name:'保存网关'})).not.toBeDisabled()
  fireEvent.change(screen.getByLabelText('名称（可选）'),{target:{value:'新名称'}})
  expect(screen.getByRole('button',{name:'保存网关'})).toBeDisabled()
  fireEvent.click(screen.getByRole('button',{name:'测试连接'}))
  await waitFor(()=>expect(screen.getByRole('button',{name:'保存网关'})).not.toBeDisabled())
  fireEvent.click(screen.getByRole('button',{name:'保存网关'}))
  await waitFor(()=>expect(screen.queryByLabelText('认证令牌（可选）')).toBeNull())
  expect(add).toHaveBeenCalledWith({url:'https://new.test/mcp',token:'private-token',name:'新名称'})
  fireEvent.click(screen.getByRole('button',{name:'添加网关'}))
  expect(screen.getByLabelText('认证令牌（可选）')).toHaveValue('')
})

it('ignores a late probe after editing and closes on outside press and Escape',async()=>{
  let finish!:(value:{url:string;identity:{available:boolean}})=>void
  render(<GatewayStatus connections={connections} onProbe={()=>new Promise(resolve=>{finish=resolve})} onAdd={vi.fn()}/>)
  const trigger=screen.getByRole('button',{name:/数据网关：/})
  fireEvent.click(trigger)
  fireEvent.click(screen.getByRole('button',{name:'添加网关'}))
  fireEvent.change(screen.getByLabelText('网关 URL'),{target:{value:'https://old.test/mcp'}})
  fireEvent.click(screen.getByRole('button',{name:'测试连接'}))
  fireEvent.change(screen.getByLabelText('网关 URL'),{target:{value:'https://different.test/mcp'}})
  finish({url:'https://old.test/mcp',identity:{available:true}})
  await waitFor(()=>expect(screen.getByRole('button',{name:'保存网关'})).toBeDisabled())
  fireEvent.pointerDown(document.body)
  expect(trigger.closest('details')?.open).toBe(false)
  fireEvent.click(trigger)
  fireEvent.keyDown(trigger,{key:'Escape'})
  expect(trigger.closest('details')?.open).toBe(false)
  expect(document.activeElement).toBe(trigger)
})

it.each([false,true])('uses the returned instance name and preserves an explicit offline flag: %s',offline=>{
  const gateway={available:true,instance_name:'已发布实例名称',connection_name:'配置连接名',endpoint:'gateway.example:8000',instance_id:'actual-instance-id',environment_label:'验证环境',data_source_label:'已发布数据源',offline}
  const base={schema:'capstone-thread-input-catalog/1',revision:'r',objects:[],materials:[],resource_profiles:{},operations:[]}
  expect(parseInputCatalog({...base,data_gateway:gateway}).data_gateway).toEqual(gateway)
  render(<GatewayStatus gateway={gateway}/>)
  const trigger=screen.getByRole('button',{name:'数据网关：已发布实例名称'})
  expect(trigger.textContent).toContain('数据网关 · 已发布实例名称')
  expect(trigger.querySelector('.lucide-database')).toBeTruthy()
  expect(trigger.textContent).not.toContain('actual-instance-id')
  fireEvent.click(trigger)
  expect(screen.getByText('验证环境')).toBeTruthy()
  expect(screen.getByText('已发布数据源')).toBeTruthy()
  expect(screen.getByText(offline?'是':'否')).toBeTruthy()
})

it('shows the actual connection and opens public service details without assuming an instance',()=>{
  render(<GatewayStatus gateway={{available:true,connection_name:'业务数据连接',server_name:'电网运行数据网关',server_version:'1.30.0',endpoint:'https://gateway.example/mcp'}}/>)
  const trigger=screen.getByRole('button',{name:'数据网关：https://gateway.example/mcp'})
  fireEvent.click(trigger)
  expect(trigger.closest('details')?.open).toBe(true)
  expect(screen.getByText('电网运行数据网关')).toBeTruthy()
  expect(screen.getByText('1.30.0')).toBeTruthy()
  expect(trigger.textContent).toContain('数据网关 · https://gateway.example/mcp')
  expect(screen.getByText('https://gateway.example/mcp')).toBeTruthy()
  expect(screen.queryByText('实例标识')).toBeNull()
  expect(screen.queryByText('离线模式')).toBeNull()
  fireEvent.keyDown(trigger.closest('details')!,{key:'Escape'})
  expect(trigger.closest('details')?.open).toBe(false)
})

it('uses the endpoint fallback and clearly shows unavailable state and a real instance ID',()=>{
  render(<GatewayStatus gateway={{available:false,endpoint:'http://gateway.example/mcp',instance_id:'actual-instance'}}/>)
  expect(screen.getAllByText('当前不可用').length).toBeGreaterThan(0)
  expect(screen.getByText('actual-instance')).toBeTruthy()
  expect(screen.getByRole('button',{name:/http:\/\/gateway.example\/mcp/})).toBeTruthy()
})

it('does not show a gateway for older catalogs',()=>{
  const {container}=render(<GatewayStatus/>)
  expect(container.textContent).toBe('')
})

it('projects only public gateway metadata and rejects credential-bearing addresses',()=>{
  const base={schema:'capstone-thread-input-catalog/1',revision:'r',objects:[],materials:[],resource_profiles:{},operations:[]}
  const parsed=parseInputCatalog({...base,data_gateway:{available:true,server_name:'网关',api_key:'secret'}})
  expect(parsed.data_gateway).toEqual({available:true,server_name:'网关'})
  expect(()=>parseInputCatalog({...base,data_gateway:{available:true,endpoint:'https://user:secret@gateway.example/mcp'}})).toThrow()
  expect(()=>parseInputCatalog({...base,data_gateway:{available:true,endpoint:'https://gateway.example/mcp?token=secret'}})).toThrow()
  for(const endpoint of ['gateway.test:8000','[::1]:443'])expect(parseInputCatalog({...base,data_gateway:{available:true,endpoint}}).data_gateway?.endpoint).toBe(endpoint)
  expect(()=>parseInputCatalog({...base,data_gateway:{available:true,endpoint:'user:secret@gateway.test:8000'}})).toThrow()
  expect(()=>parseInputCatalog({...base,data_gateway:{available:true,offline:'false'}})).toThrow()
})
