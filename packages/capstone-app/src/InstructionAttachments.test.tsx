import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react'
import CapstoneAssistantThread,{projectAssistantMessages} from './CapstoneAssistantThread'
import InstructionAttachments from './InstructionAttachments'
import {applicationCapacity} from './applicationCapacity'
import type {EventEnvelope} from './threadProtocol'
import type {InputCatalog} from './threadInput'
afterEach(()=>{cleanup();sessionStorage.clear()})
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
