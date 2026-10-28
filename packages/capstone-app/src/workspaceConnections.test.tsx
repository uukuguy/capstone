import {afterEach,expect,it,vi} from 'vitest'
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {useWorkspaceConnections,type WorkspaceConnections} from './workspaceConnections'
import {SessionConnectionStatus} from './WorkspaceConnectionStatus'
import {HttpThreadTransport} from './threadHttpTransport'

afterEach(cleanup)
const data=(instance_name:string):WorkspaceConnections=>({schema:'capstone-workspace-connections/1',data_gateway:{available:true,instance_name}})
function Probe({transport,id}:{transport:{workspaceConnections:()=>Promise<WorkspaceConnections>};id:string}){
  const state=useWorkspaceConnections(transport)
  return <div><output data-testid={id}>{state.data?.data_gateway?.instance_name}</output><button onClick={()=>void state.refresh()}>刷新{id}</button>{state.error&&<p>{state.error}</p>}</div>
}
it('shares global metadata between session mounts and keeps separate transports isolated',async()=>{
  const transport={workspaceConnections:vi.fn().mockResolvedValue(data('实例 A'))}
  const view=render(<><Probe transport={transport} id="one"/><Probe transport={transport} id="two"/></>)
  await waitFor(()=>expect(screen.getByTestId('one').textContent).toBe('实例 A'))
  expect(screen.getByTestId('two').textContent).toBe('实例 A')
  expect(transport.workspaceConnections).toHaveBeenCalledTimes(1)
  view.rerender(<Probe key="another-session" transport={transport} id="other"/>)
  expect(screen.getByTestId('other').textContent).toBe('实例 A')
  expect(transport.workspaceConnections).toHaveBeenCalledTimes(1)
  const second={workspaceConnections:vi.fn().mockResolvedValue(data('实例 B'))}
  view.rerender(<Probe transport={second} id="other"/>)
  await waitFor(()=>expect(screen.getByTestId('other').textContent).toBe('实例 B'))
})
it('retains the current gateway while refresh fails without declaring MCP unavailable',async()=>{
  const transport={workspaceConnections:vi.fn().mockResolvedValueOnce(data('已确认实例')).mockRejectedValue(new Error('read unavailable'))}
  render(<Probe transport={transport} id="one"/>)
  await waitFor(()=>expect(screen.getByTestId('one').textContent).toBe('已确认实例'))
  await act(async()=>{fireEvent.click(screen.getByText('刷新one'))})
  expect(screen.getByTestId('one').textContent).toBe('已确认实例')
  expect(screen.getByText('网关连接信息暂未更新。')).toBeTruthy()
})
it('shares the same workspace scope across retained session HTTP transports',async()=>{
  const fetcher=vi.fn<typeof fetch>().mockImplementation(async()=>new Response(JSON.stringify(data('共享实例')),{headers:{'Capstone-Thread-Version':'2'}}))
  const first=new HttpThreadTransport('https://shared-api.example','auth-one',fetcher,'/api/v1/threads','2')
  const second=new HttpThreadTransport('https://shared-api.example','auth-one',fetcher,'/api/v1/threads','2')
  expect(first.workspaceConnectionsScope).toBe(second.workspaceConnectionsScope)
  expect(new HttpThreadTransport('https://shared-api.example','other-auth',fetcher).workspaceConnectionsScope).not.toBe(first.workspaceConnectionsScope)
  const view=render(<Probe transport={first} id="one"/>)
  await waitFor(()=>expect(screen.getByTestId('one').textContent).toBe('共享实例'))
  view.rerender(<Probe key="retained-session" transport={second} id="two"/>)
  expect(screen.getByTestId('two').textContent).toBe('共享实例')
  expect(fetcher).toHaveBeenCalledTimes(1)
})
it('keeps one short session connection slot and exposes pending request semantics in details',()=>{
  const view=render(<SessionConnectionStatus state="disconnected" error="实际实时连接错误" recovering/>)
  expect(screen.getAllByText('连接恢复中')).toHaveLength(1)
  const summary=screen.getByText('连接恢复中')
  fireEvent.click(summary)
  expect(summary.closest('details')?.open).toBe(true)
  expect(screen.getByText('实际实时连接错误')).toBeTruthy()
  view.rerender(<SessionConnectionStatus state="live" pending/>)
  expect(screen.getByText('操作待确认')).toBeTruthy()
  expect(screen.getByText('上次操作结果待确认；重试将使用同一请求。')).toBeTruthy()
})
