import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import {useGatewayConnections} from './gatewayConnectionsStore'
import type {GatewayConnections} from './gatewayConnectionTypes'

afterEach(cleanup)
const value=(selected_id='one',revision=1):GatewayConnections=>({schema:'capstone-gateway-connections/1',revision,selected_id,checking:false,entries:[
  {id:'one',label:'联调',url:'http://localhost:18001/mcp',status:'connected'},
  {id:'two',label:'研发',url:'http://localhost:18003/mcp',status:'connected'}]})
type Transport=Parameters<typeof useGatewayConnections>[0]
function Probe({transport,id}:{transport:Transport;id:string}){
  const state=useGatewayConnections(transport)
  return <div><span data-testid={id}>{state.data?.selected_id}</span><button onClick={()=>void state.select('two').catch(()=>{})}>切换{id}</button>{state.error&&<p>{state.error}</p>}</div>
}
it('shares the selection across retained session transports with one global snapshot',async()=>{
  const scope={},load=vi.fn().mockResolvedValue(value()),select=vi.fn().mockResolvedValue(value('two',2))
  const first={workspaceConnectionsScope:scope,gatewayConnections:load,selectGatewayConnection:select}
  render(<><Probe transport={first} id="a"/><Probe transport={{...first}} id="b"/></>)
  await waitFor(()=>expect(screen.getByTestId('a').textContent).toBe('one'))
  expect(load).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByText('切换a'))
  await waitFor(()=>expect(screen.getByTestId('b').textContent).toBe('two'))
  expect(screen.getByTestId('a').textContent).toBe('two')
  expect(select).toHaveBeenCalledExactlyOnceWith('two')
})
it('retains the confirmed selection when a switch fails without retrying the write',async()=>{
  const select=vi.fn().mockRejectedValue(new Error('有任务正在执行，请结束后切换网关。'))
  render(<Probe transport={{gatewayConnections:async()=>value(),selectGatewayConnection:select}} id="a"/>)
  await waitFor(()=>expect(screen.getByTestId('a').textContent).toBe('one'))
  fireEvent.click(screen.getByText('切换a'))
  expect(await screen.findByText('有任务正在执行，请结束后切换网关。')).toBeTruthy()
  expect(screen.getByTestId('a').textContent).toBe('one')
  expect(select).toHaveBeenCalledTimes(1)
})

it('notifies retained consumers when another client changes the global connection',async()=>{
  const changed=vi.fn(),load=vi.fn().mockResolvedValueOnce(value()).mockResolvedValue(value('two',2))
  window.addEventListener('capstone-gateway-changed',changed)
  try{
    render(<Probe transport={{gatewayConnections:load}} id="a"/>)
    await waitFor(()=>expect(screen.getByTestId('a').textContent).toBe('one'))
    fireEvent.focus(window)
    await waitFor(()=>expect(screen.getByTestId('a').textContent).toBe('two'))
    expect(changed).toHaveBeenCalledTimes(1)
  }finally{window.removeEventListener('capstone-gateway-changed',changed)}
})
