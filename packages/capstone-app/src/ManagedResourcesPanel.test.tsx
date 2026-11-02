import '@testing-library/jest-dom/vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import ManagedResourcesPanel from './ManagedResourcesPanel'

afterEach(cleanup)
const resource={resource_id:'research-tools',version:'v1',kind:'skill',installed:true,enabled:true,
  available:false,diagnostics:['connection unavailable'],source:{locator:'https://example.test/repo',revision:'a'.repeat(40)}}
function transport(actions:string[]=[],resources:(typeof resource&{preinstall?:{drafts:string[];published:string[]};installation?:{subdirectory:string;runtime?:{entrypoint:string}}})[]=[resource]){
  return {listManagedResources:vi.fn().mockResolvedValue({revision:'catalog-1',allowed_actions:actions.map(a=>`resources.${a}`),resources}),
    manageResource:vi.fn().mockResolvedValue({status:'installed',available:false}),
    readManagedResourceOperation:vi.fn().mockResolvedValue({status:'pending'})}
}
async function open(client:ReturnType<typeof transport>){
  render(<ManagedResourcesPanel transport={client}/> )
  expect(client.listManagedResources).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'Skills / MCP 管理'}))
  await screen.findByText('research-tools')
}
async function installForm(client:ReturnType<typeof transport>,kind='skill'){
  await open(client)
  fireEvent.change(screen.getByLabelText('类型'),{target:{value:kind}})
  fireEvent.change(screen.getByLabelText('资源标识'),{target:{value:'new-tools'}})
  fireEvent.change(screen.getByLabelText(kind==='mcp_remote'?'MCP 服务地址':'Git 仓库地址'),{target:{value:'https://example.test/source'}})
}

it('keeps installation and management closed when policy grants use only',async()=>{
  const client=transport(['use'])
  await open(client)
  expect(screen.getByRole('dialog',{name:'Skills 与 MCP 管理'})).toBeInTheDocument()
  expect(screen.queryByRole('button',{name:'安装并校验'})).not.toBeInTheDocument()
  for(const name of ['停用','启用','卸载','加入预安装草稿','发布预安装清单'])expect(screen.queryByRole('button',{name})).not.toBeInTheDocument()
  expect(screen.getByText(/不可用/)).toBeInTheDocument()
  expect(screen.getByText('connection unavailable')).toBeInTheDocument()
  expect(client.manageResource).not.toHaveBeenCalled()
})

it('submits an exact pinned Skill installation request',async()=>{
  const client=transport(['install'])
  await installForm(client)
  fireEvent.change(screen.getByLabelText('Git 完整提交哈希'),{target:{value:'b'.repeat(40)}})
  fireEvent.change(screen.getByLabelText('仓库内目录'),{target:{value:'skills/research'}})
  fireEvent.click(screen.getByRole('button',{name:'安装并校验'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenCalledWith('install',{
    request_id:expect.any(String),resource_id:'new-tools',request:{kind:'skill',source:{locator:'https://example.test/source',revision:'b'.repeat(40)},
      subdirectory:'skills/research',runtime:{entrypoint:''}}}))
})

it('discovers a remote MCP contract without sending local runtime fields',async()=>{
  const client=transport(['install'])
  await installForm(client,'mcp_remote')
  expect(screen.queryByLabelText('仓库内目录')).not.toBeInTheDocument()
  expect(screen.queryByLabelText('启动文件')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'安装并校验'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenCalledWith('install',{
    request_id:expect.any(String),resource_id:'new-tools',request:{kind:'mcp_remote',source:{locator:'https://example.test/source',revision:'discover'}}}))
  expect(screen.queryByText('安装成功')).not.toBeInTheDocument()
})

it('sends the selected entrypoint for local MCP installation',async()=>{
  const client=transport(['install'])
  await installForm(client,'mcp_local')
  fireEvent.change(screen.getByLabelText('Git 完整提交哈希'),{target:{value:'c'.repeat(40)}})
  fireEvent.change(screen.getByLabelText('启动文件'),{target:{value:'server.mjs'}})
  fireEvent.click(screen.getByRole('button',{name:'安装并校验'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenCalledWith('install',expect.objectContaining({request:{kind:'mcp_local',
    source:{locator:'https://example.test/source',revision:'c'.repeat(40)},subdirectory:'',runtime:{entrypoint:'server.mjs'}}})))
})

it('gates state changes separately and binds them to the current version',async()=>{
  const client=transport(['disable'])
  await open(client)
  expect(screen.queryByRole('button',{name:'卸载'})).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'停用'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenCalledWith('state',{resource_id:'research-tools',expected_version:'v1',enabled:false}))
})

it('permits enable and uninstall only with their own grants',async()=>{
  const client=transport(['enable','uninstall'],[{...resource,enabled:false}])
  await open(client)
  fireEvent.click(screen.getByRole('button',{name:'启用'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenCalledWith('state',{resource_id:'research-tools',expected_version:'v1',enabled:true}))
  await waitFor(()=>expect(screen.getByRole('button',{name:'卸载'})).not.toBeDisabled())
  fireEvent.click(screen.getByRole('button',{name:'卸载'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenLastCalledWith('uninstall',{resource_id:'research-tools',expected_version:'v1'}))
})

it('keeps preinstallation management separate from install permission and deployment',async()=>{
  const client=transport(['preinstall.manage'])
  await open(client)
  expect(screen.queryByRole('button',{name:'安装并校验'})).not.toBeInTheDocument()
  for(const [name,operation,payload] of [
    ['加入预安装草稿','preinstall_draft',{profile:'default',resource_id:'research-tools',include:true}],
    ['查看预安装草稿','preinstall_export',{profile:'default'}],
    ['发布预安装清单','preinstall_publish',{profile:'default'}],
  ] as const){
    await waitFor(()=>expect(screen.getByRole('button',{name})).not.toBeDisabled())
    fireEvent.click(screen.getByRole('button',{name}))
    await waitFor(()=>expect(client.manageResource).toHaveBeenLastCalledWith(operation,payload))
  }
  expect(screen.getByText('发布清单不代表已更新其他服务器。')).toBeInTheDocument()
})

it('reports a denied operation without inventing success or changing installed state',async()=>{
  const client=transport(['disable'])
  client.manageResource.mockRejectedValue(new Error('permission revoked'))
  await open(client)
  fireEvent.click(screen.getByRole('button',{name:'停用'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('permission revoked')
  expect(screen.queryByRole('region',{name:'资源操作结果'})).not.toBeInTheDocument()
  expect(screen.getByRole('button',{name:'停用'})).not.toBeDisabled()
  expect(client.listManagedResources).toHaveBeenCalledTimes(1)
})

it('shows failed validation as unavailable and retains the returned receipt',async()=>{
  const client=transport(['disable'])
  client.manageResource.mockResolvedValue({status:'failed',available:false,diagnostics:['load failed']})
  await open(client)
  fireEvent.click(screen.getByRole('button',{name:'停用'}))
  const receipt=await screen.findByRole('region',{name:'资源操作结果'})
  expect(within(receipt).getByText(/"status": "failed"/)).toBeInTheDocument()
  expect(screen.getByText(/不可用/)).toBeInTheDocument()
  expect(screen.queryByText('安装成功')).not.toBeInTheDocument()
})

it('reports catalog read failures without enabling operations',async()=>{
  const client=transport(['install'])
  client.listManagedResources.mockRejectedValue(new Error('catalog unavailable'))
  render(<ManagedResourcesPanel transport={client}/> )
  fireEvent.click(screen.getByRole('button',{name:'Skills / MCP 管理'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('catalog unavailable')
  expect(screen.queryByRole('button',{name:'安装并校验'})).not.toBeInTheDocument()
  expect(client.manageResource).not.toHaveBeenCalled()
})

it('blocks duplicate mutations while an operation is pending',async()=>{
  const client=transport(['disable','uninstall','preinstall.manage'])
  let resolve!:(value:unknown)=>void
  client.manageResource.mockImplementation(()=>new Promise(done=>{resolve=done}))
  await open(client)
  fireEvent.click(screen.getByRole('button',{name:'停用'}))
  for(const name of ['停用','卸载','加入预安装草稿','查看预安装草稿','发布预安装清单']){
    expect(screen.getByRole('button',{name})).toBeDisabled()
    fireEvent.click(screen.getByRole('button',{name}))
  }
  expect(client.manageResource).toHaveBeenCalledTimes(1)
  resolve({status:'disabled'})
  await waitFor(()=>expect(screen.getByRole('button',{name:'停用'})).not.toBeDisabled())
})

it('permits a pinned version update without granting new installation',async()=>{
  const client=transport(['update'])
  await open(client)
  expect(screen.queryByRole('button',{name:'安装并校验'})).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:/^更新$/}))
  expect(screen.getByLabelText('资源标识')).toBeDisabled()
  expect(screen.getByLabelText('资源标识')).toHaveValue('research-tools')
  expect(screen.getByLabelText('Git 仓库地址')).toHaveValue(resource.source.locator)
  fireEvent.change(screen.getByLabelText('Git 完整提交哈希'),{target:{value:'d'.repeat(40)}})
  fireEvent.click(screen.getByRole('button',{name:'更新并校验'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenCalledWith('install',{
    request_id:expect.any(String),resource_id:'research-tools',expected_version:'v1',request:{kind:'skill',
      source:{locator:resource.source.locator,revision:'d'.repeat(40)},subdirectory:'',runtime:{entrypoint:''}}}))
})

it('distinguishes an existing preinstall draft from a published undeployed manifest',async()=>{
  const client=transport(['use'],[{...resource,preinstall:{drafts:['draft-profile'],published:['released-profile']}}])
  await open(client)
  expect(screen.getByText('已加入预装草稿：draft-profile')).toBeInTheDocument()
  expect(screen.getByText('已发布预装清单：released-profile（不代表已部署）')).toBeInTheDocument()
  expect(screen.queryByText('已随部署提供')).not.toBeInTheDocument()
  expect(client.manageResource).not.toHaveBeenCalled()
})

it('retries a failed catalog read without reopening the panel',async()=>{
  const client=transport(['update'])
  client.listManagedResources.mockRejectedValueOnce(new Error('catalog unavailable'))
  render(<ManagedResourcesPanel transport={client}/> )
  fireEvent.click(screen.getByRole('button',{name:'Skills / MCP 管理'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('catalog unavailable')
  expect(screen.queryByText('正在读取资源…')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:'重试读取'}))
  await screen.findByText('research-tools')
  expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  expect(client.listManagedResources).toHaveBeenCalledTimes(2)
})

it('restores validated update metadata and uses the refreshed version after success',async()=>{
  const installed={...resource,installation:{subdirectory:'skills/pinned',runtime:{entrypoint:'server.mjs'}}}
  const client=transport(['update'],[installed])
  await open(client)
  expect(screen.getByText('当前未开放安装权限；其他操作以各自权限为准。')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button',{name:/^更新$/}))
  expect(screen.getByLabelText('仓库内目录')).toHaveValue('skills/pinned')
  fireEvent.change(screen.getByLabelText('仓库内目录'),{target:{value:'unrelated-draft'}})
  fireEvent.click(screen.getByRole('button',{name:'取消更新'}))
  fireEvent.click(screen.getByRole('button',{name:/^更新$/}))
  expect(screen.getByLabelText('仓库内目录')).toHaveValue('skills/pinned')
  fireEvent.change(screen.getByLabelText('Git 完整提交哈希'),{target:{value:'e'.repeat(40)}})
  client.manageResource.mockResolvedValue({status:'succeeded'})
  client.listManagedResources.mockResolvedValue({revision:'catalog-2',allowed_actions:['resources.update'],resources:[{...installed,version:'v2'}]})
  fireEvent.click(screen.getByRole('button',{name:'更新并校验'}))
  await waitFor(()=>expect(screen.queryByRole('button',{name:'更新并校验'})).not.toBeInTheDocument())
  fireEvent.click(screen.getByRole('button',{name:/^更新$/}))
  fireEvent.change(screen.getByLabelText('Git 完整提交哈希'),{target:{value:'f'.repeat(40)}})
  fireEvent.click(screen.getByRole('button',{name:'更新并校验'}))
  await waitFor(()=>expect(client.manageResource).toHaveBeenLastCalledWith('install',expect.objectContaining({expected_version:'v2',
    request:expect.objectContaining({subdirectory:'skills/pinned',runtime:{entrypoint:'server.mjs'}})})))
})

it('retains an install request before disconnect and recovers by lookup without replay',async()=>{
  const client=transport(['install'])
  client.manageResource.mockRejectedValue(new Error('connection lost'))
  await installForm(client,'mcp_remote')
  fireEvent.click(screen.getByRole('button',{name:'安装并校验'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('connection lost')
  const requestId=client.manageResource.mock.calls[0][1].request_id
  expect(screen.getByLabelText('查询请求编号')).toHaveValue(requestId)
  expect(screen.getByRole('button',{name:'安装并校验'})).toBeDisabled()
  client.readManagedResourceOperation.mockResolvedValue({request_id:requestId,status:'succeeded'})
  fireEvent.click(screen.getByRole('button',{name:'查询原操作'}))
  await waitFor(()=>expect(client.readManagedResourceOperation).toHaveBeenCalledWith(requestId))
  await waitFor(()=>expect(screen.getByRole('button',{name:'安装并校验'})).not.toBeDisabled())
  expect(client.manageResource).toHaveBeenCalledTimes(1)
})

it('looks up pending operations explicitly and retains unknown status on read failure',async()=>{
  const client=transport(['install'])
  client.manageResource.mockResolvedValue({request_id:'pending-request',status:'pending'})
  await installForm(client,'mcp_remote')
  fireEvent.click(screen.getByRole('button',{name:'安装并校验'}))
  await screen.findByText(/操作尚未确认完成/)
  expect(client.readManagedResourceOperation).not.toHaveBeenCalled()
  client.readManagedResourceOperation.mockRejectedValue(new Error('lookup unavailable'))
  fireEvent.click(screen.getByRole('button',{name:'查询原操作'}))
  expect(await screen.findByRole('alert')).toHaveTextContent('lookup unavailable')
  expect(screen.getByRole('button',{name:'安装并校验'})).toBeDisabled()
  expect(client.manageResource).toHaveBeenCalledTimes(1)
})

it('can query a saved request id without install permission or a new install',async()=>{
  const client=transport(['use'])
  await open(client)
  fireEvent.change(screen.getByLabelText('查询请求编号'),{target:{value:'saved-request'}})
  fireEvent.click(screen.getByRole('button',{name:'查询原操作'}))
  await waitFor(()=>expect(client.readManagedResourceOperation).toHaveBeenCalledWith('saved-request'))
  expect(client.manageResource).not.toHaveBeenCalled()
})

it('shows the original request id while dispatch is pending and retains it after closing',async()=>{
  const client=transport(['install'])
  let resolve!:(value:unknown)=>void
  client.manageResource.mockImplementation(()=>new Promise(done=>{resolve=done}))
  await installForm(client,'mcp_remote')
  fireEvent.click(screen.getByRole('button',{name:'安装并校验'}))
  const requestId=client.manageResource.mock.calls[0][1].request_id
  expect(screen.getByLabelText('查询请求编号')).toHaveValue(requestId)
  fireEvent.click(screen.getByRole('button',{name:'关闭资源管理'}))
  fireEvent.click(screen.getByRole('button',{name:'Skills / MCP 管理'}))
  expect(screen.getByLabelText('查询请求编号')).toHaveValue(requestId)
  expect(client.manageResource).toHaveBeenCalledTimes(1)
  resolve({request_id:requestId,status:'pending'})
  await waitFor(()=>expect(screen.getByRole('button',{name:'查询原操作'})).not.toBeDisabled())
  expect(client.readManagedResourceOperation).not.toHaveBeenCalled()
})
