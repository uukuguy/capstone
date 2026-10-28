import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import GatewayStatus from './GatewayStatus'
import {parseInputCatalog} from './threadInput'

afterEach(cleanup)

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
