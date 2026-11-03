import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import {WorkspaceGatewayStatus} from './WorkspaceConnectionStatus'
import type {HttpThreadTransport} from './threadHttpTransport'
import type {GatewayConnections} from './gatewayConnectionTypes'

afterEach(cleanup)
const data=(id:string,locked:boolean):GatewayConnections=>({schema:'capstone-gateway-connections/1',revision:1,checking:false,selected_id:id,locked,
  entries:[{id:'one',label:'实例 A',url:'http://one.example/mcp',status:'connected'},{id:'two',label:'实例 B',url:'http://two.example/mcp',status:'connected'}]})

it('changes the sidebar identity and lock with the selected session without showing the global default',async()=>{
 const onConnection=vi.fn()
 const select=vi.fn().mockResolvedValue(data('one',false))
 const transport={
  workspaceConnections:vi.fn().mockResolvedValue({schema:'capstone-workspace-connections/1',data_gateway:{available:true,instance_name:'全局默认实例'}}),
  threadGatewayConnections:vi.fn(async(id:string)=>id==='thr_a'?data('one',true):data('two',false)),
  selectThreadGatewayConnection:select,refreshGatewayConnections:vi.fn(),refreshThreadGatewayContract:vi.fn(),
  probeGatewayConnection:vi.fn(),addGatewayConnection:vi.fn(),
 } as unknown as HttpThreadTransport
 const view=render(<WorkspaceGatewayStatus transport={transport} threadId="thr_a" onConnection={onConnection}/>);
 fireEvent.click(await screen.findByRole('button',{name:'数据网关：实例 A'}));
 expect(onConnection).toHaveBeenLastCalledWith(expect.objectContaining({instance_name:'实例 A',endpoint:'http://one.example/mcp'}))
 fireEvent.click(screen.getByRole('button',{name:/实例 B.*可连接/}));
 expect(screen.getByRole('button',{name:'使用此网关'})).toBeDisabled();
 view.rerender(<WorkspaceGatewayStatus transport={transport} threadId="thr_b" onConnection={onConnection}/>);
 fireEvent.click(await screen.findByRole('button',{name:'数据网关：实例 B'}));
 expect(onConnection).toHaveBeenLastCalledWith(expect.objectContaining({instance_name:'实例 B',endpoint:'http://two.example/mcp'}))
 expect(screen.queryByText('全局默认实例')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:/实例 A.*可连接/}));
 expect(screen.getByRole('button',{name:'使用此网关'})).not.toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'使用此网关'}));
 await waitFor(()=>expect(select).toHaveBeenCalledWith('thr_b','one'));
})
