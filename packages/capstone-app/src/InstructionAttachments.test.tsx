import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import CapstoneAssistantThread,{projectAssistantMessages} from './CapstoneAssistantThread'
import InstructionAttachments,{type InstructionFile} from './InstructionAttachments'
import {applicationCapacity} from './applicationCapacity'
import type {EventEnvelope} from './threadProtocol'
import type {InputCatalog} from './threadInput'
afterEach(()=>{cleanup();sessionStorage.clear()})
it('shows a download error while the preview is closed',async()=>{
  render(<InstructionAttachments files={[{resource_id:'resource_error',file_name:'error.txt',size_bytes:8,sha256:'a'.repeat(64)}]} readFile={async()=>{throw new Error('读取失败')}}/>)
  fireEvent.click(screen.getByRole('button',{name:'下载附件 error.txt'}))
  expect((await screen.findByRole('alert')).textContent).toContain('读取失败')
})
it('aborts an obsolete preview and does not create a late object URL',async()=>{
  const create=vi.fn(()=> 'blob:late')
  vi.stubGlobal('URL',class extends URL{static createObjectURL=create;static revokeObjectURL=vi.fn()})
  let finish!:(value:Uint8Array)=>void
  let signal:AbortSignal|undefined
  const read=vi.fn((_file:InstructionFile,value?:AbortSignal)=>{signal=value;return new Promise<Uint8Array>(resolve=>{finish=resolve})})
  render(<InstructionAttachments files={[{resource_id:'resource_slow',file_name:'slow.txt',size_bytes:8,sha256:'a'.repeat(64)}]} readFile={read}/>)
  fireEvent.click(screen.getByRole('button',{name:'预览附件 slow.txt'}))
  fireEvent.click(screen.getByRole('button',{name:'收起附件 slow.txt'}))
  expect(signal?.aborted).toBe(true)
  finish(new Uint8Array([65]))
  await waitFor(()=>expect(create).not.toHaveBeenCalled())
})
it('releases loaded preview bytes when collapsed',async()=>{
  const revoke=vi.fn()
  vi.stubGlobal('URL',class extends URL{static createObjectURL=vi.fn(()=> 'blob:release');static revokeObjectURL=revoke})
  render(<InstructionAttachments files={[{resource_id:'resource_release',file_name:'release.txt',size_bytes:8,sha256:'a'.repeat(64)}]} readFile={async()=>new TextEncoder().encode('正文')}/>)
  fireEvent.click(screen.getByRole('button',{name:'预览附件 release.txt'}))
  await screen.findByText('正文')
  fireEvent.click(screen.getByRole('button',{name:'收起附件 release.txt'}))
  expect(revoke).toHaveBeenCalledWith('blob:release')
})
it('shares an in-flight read between preview and download',async()=>{
  vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{})
  vi.stubGlobal('URL',class extends URL{static createObjectURL=vi.fn(()=> 'blob:shared');static revokeObjectURL=vi.fn()})
  let finish!:(value:Uint8Array)=>void
  const read=vi.fn(()=>new Promise<Uint8Array>(resolve=>{finish=resolve}))
  render(<InstructionAttachments files={[{resource_id:'resource_shared',file_name:'shared.txt',size_bytes:8,sha256:'a'.repeat(64)}]} readFile={read}/>)
  fireEvent.click(screen.getByRole('button',{name:'预览附件 shared.txt'}))
  fireEvent.click(screen.getByRole('button',{name:'下载附件 shared.txt'}))
  expect(read).toHaveBeenCalledTimes(1)
  finish(new TextEncoder().encode('共享正文'))
  await screen.findByText('共享正文')
  expect(read).toHaveBeenCalledTimes(1)
  vi.restoreAllMocks()
})
const one=`resource_${'a'.repeat(32)}`,two=`resource_${'b'.repeat(32)}`
const events:EventEnvelope[]=[one,two].map((id,i)=>({eventId:`event_${i}`,eventSeq:i+1,eventType:'command_accepted',eventVersion:1,threadId:'thread',runId:'run',attemptId:`attempt_${i}`,occurredAt:'2026-10-28T00:00:00Z',visibility:'public',payload:{kind:'send_auto',attachment_refs:[id],payload:{text:`指令${i+1}`}}}))
const catalog:InputCatalog={schema:'capstone-thread-input-catalog/1',revision:'catalog',context_id:'none',selection_revision:'selection',objects:[],materials:[],resource_profiles:{},operations:[],stored_resources:[one,two].map((id,i)=>({schema:'capstone-resource/1',resource_id:id,thread_id:'thread',version:1,file_name:`资料${i+1}.csv`,size_bytes:2048,sha256:'a'.repeat(64),processing_state:'stored'}))}
it('retains exact attachment ownership in accepted instruction projection',()=>{
  const users=projectAssistantMessages(events).filter(message=>message.role==='user')
  expect(users.map(message=>message.metadata?.custom?.attachmentRefs)).toEqual([[one],[two]])
})
it('shows files beside their instruction after catalog reload without copying file bodies',()=>{
  const props={events,disabled:false,isRunning:false,activity:[],onSend:vi.fn(async()=>{}),onCancel:async()=>{}}
  const view=render(<CapstoneAssistantThread {...props}/>)
  expect(screen.getAllByLabelText('指令附件')).toHaveLength(2)
  view.rerender(<CapstoneAssistantThread {...props} inputCatalog={catalog}/>)
  const users=screen.getAllByLabelText('用户指令')
  expect(within(users[0]).getByText('资料1.csv')).toBeTruthy()
  expect(within(users[0]).queryByText('资料2.csv')).toBeNull()
  expect(within(users[1]).getByText('资料2.csv')).toBeTruthy()
  expect(within(users[1]).queryByText('资料1.csv')).toBeNull()
  expect(screen.queryByLabelText('待发送附件')).toBeNull()
  expect(screen.queryByRole('button',{name:/预览附件/})).toBeNull()
})
it('offers preview and download only on the instruction that owns the file',()=>{
  const props={events,disabled:false,isRunning:false,activity:[],onSend:vi.fn(async()=>{}),onCancel:async()=>{},inputCatalog:catalog,readInstructionFile:vi.fn(async()=>new Uint8Array())}
  render(<CapstoneAssistantThread {...props}/>)
  const users=screen.getAllByLabelText('用户指令')
  expect(within(users[0]).getByRole('button',{name:'预览附件 资料1.csv'})).toBeTruthy()
  expect(within(users[0]).getByRole('button',{name:'下载附件 资料1.csv'})).toBeTruthy()
  expect(within(users[0]).queryByRole('button',{name:'预览附件 资料2.csv'})).toBeNull()
  expect(within(users[1]).getByRole('button',{name:'预览附件 资料2.csv'})).toBeTruthy()
  expect(within(users[1]).queryByRole('button',{name:'下载附件 资料1.csv'})).toBeNull()
})
it('previews and downloads instruction bytes only after the reader is used',async()=>{
  vi.stubGlobal('URL',class extends URL{static createObjectURL=vi.fn(()=> 'blob:attachment');static revokeObjectURL=vi.fn()})
  const bytes=new TextEncoder().encode('# 手册正文\n')
  const read=vi.fn(async()=>bytes)
  render(<InstructionAttachments files={[{resource_id:one,file_name:'01-安装部署手册.md',size_bytes:bytes.byteLength,version:1,sha256:'a'.repeat(64)}]} readFile={read}/>)
  expect(screen.queryByText('手册正文')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'预览附件 01-安装部署手册.md'}))
  expect(await screen.findByText('手册正文')).toBeTruthy()
  expect(read).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByRole('button',{name:'下载附件 01-安装部署手册.md'}))
  await waitFor(()=>expect(read).toHaveBeenCalledTimes(1))
})
it('opens one attachment preview at a time and closes it',async()=>{
  const read=vi.fn(async(file:InstructionFile)=>new TextEncoder().encode(file.resource_id===one?'正文甲\n':'正文乙\n'))
  const files=[
    {resource_id:one,file_name:'一.txt',size_bytes:8,version:1,sha256:'a'.repeat(64)},
    {resource_id:two,file_name:'二.txt',size_bytes:8,version:1,sha256:'b'.repeat(64)},
  ]
  render(<InstructionAttachments files={files} readFile={read}/>)
  fireEvent.click(screen.getByRole('button',{name:'预览附件 一.txt'}))
  expect(await screen.findByText('正文甲')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'预览附件 二.txt'}))
  expect(await screen.findByText('正文乙')).toBeTruthy()
  expect(screen.queryByText('正文甲')).toBeNull()
  expect(screen.getByRole('button',{name:'收起附件 二.txt'})).toBeTruthy()
  expect(screen.getByRole('button',{name:'预览附件 一.txt'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'收起附件 二.txt'}))
  expect(screen.queryByText('正文乙')).toBeNull()
  expect(screen.getByRole('button',{name:'预览附件 二.txt'})).toBeTruthy()
})
it('shows the preview limit without reading a larger instruction file',async()=>{
  const read=vi.fn(async()=>new Uint8Array([1]))
  const save=vi.fn(async()=>undefined)
  render(<InstructionAttachments files={[{resource_id:one,file_name:'01-安装部署手册.pdf',size_bytes:applicationCapacity('artifact_file_bytes')+1,version:1,sha256:'b'.repeat(64)}]} readFile={read} saveFile={save}/>)
  fireEvent.click(screen.getByRole('button',{name:'预览附件 01-安装部署手册.pdf'}))
  expect(await screen.findByText(/超过内置预览容量/)).toBeTruthy()
  expect(read).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button',{name:'下载附件 01-安装部署手册.pdf'}))
  await waitFor(()=>expect(save).toHaveBeenCalledTimes(1))
  expect(read).not.toHaveBeenCalled()
})
