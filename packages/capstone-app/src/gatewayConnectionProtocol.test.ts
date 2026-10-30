import {expect,it} from 'vitest'
import {parseGatewayConnections,parseGatewayProbe} from './gatewayConnectionProtocol'

it('admits only public connection fields and rejects credential-bearing URLs',()=>{
  const row={id:'one',label:'本地联调',url:'http://localhost:18001/mcp',status:'connected',token:'private',identity:{available:true,instance_name:'真实网关',password:'private'}}
  const value=parseGatewayConnections({schema:'capstone-gateway-connections/1',revision:1,selected_id:'one',entries:[row],checking:false,headers:{Authorization:'private'}})
  expect(JSON.stringify(value)).not.toContain('private')
  expect(value.entries[0].identity?.instance_name).toBe('真实网关')
  expect(()=>parseGatewayProbe({url:'http://user:private@host/mcp',identity:{available:true}})).toThrow()
  expect(()=>parseGatewayConnections({...value,selected_id:'missing'})).toThrow()
})
