import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient } from './threadClient'
import { createFixtureTransport } from './threadProjectionStore'
import { threadUiFixture } from './threadUiFixtures'
import type { EventEnvelope } from './threadProtocol'
import App from './App'
import {parseProductRef} from './threadProducts'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); localStorage.clear(); window.history.replaceState({},'', '/') })

it('selects an exact historical product in the shared professional workspace and submits it as context',async()=>{
  const fixture=threadUiFixture('idle-ieee39'),base=createFixtureTransport(fixture)
  const ref=parseProductRef({schema:'capstone-product-ref/1',thread_id:'thr_demo_39',product_id:'product_old_record',origin:'process_record',scope:'instruction',event_seq:8,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:'old_attempt',producer_attempt_id:null})
  const record={thread_id:'thr_demo_39',attempt_id:'old_attempt',instruction:'旧校核说明',status:'failed',failure_code:'data_missing'}
  const entry={ref,title:'旧校核说明',media_type:null,byte_size:null,source_status:'failed',created_at:'2026-10-17T00:00:00Z',download_url:null,source:record,dependencies:[],presentation:{kind:'process_record' as const},capabilities:{read:true as const,select:true},selection_unavailable_reason:null,historical_only:true as const}
  const send=vi.fn(base.sendCommand)
  const transport={...base,sendCommand:send,readProductIndex:vi.fn(async(_thread:string,_query?:unknown)=>({products:[entry],hasMore:false,nextCursor:null})),resolveProduct:vi.fn(async()=>({entry,bytes:null,projection:null,record}))}
  render(<ThreadFixtureApp client={new CapstoneThreadClient(transport)} threadId="thr_demo_39" presentation="workspace"/>)
  const input=await screen.findByRole('textbox',{name:'Thread 指令'})
  fireEvent.click(screen.getByRole('button',{name:'打开成果目录'}))
  fireEvent.click(await screen.findByRole('button',{name:'查看：旧校核说明'}))
  fireEvent.click(await screen.findByRole('button',{name:'引用到下一轮'}))
  await screen.findByRole('button',{name:'移除成果引用：旧校核说明'})
  fireEvent.change(input,{target:{value:'保留这个失败记录，继续检查'}})
  fireEvent.click(screen.getByRole('button',{name:'发送指令'}))
  await waitFor(()=>expect(send).toHaveBeenCalled())
  expect(send.mock.calls[0][0]).toMatchObject({kind:'send_auto',payload:{context_product_refs:[{ref,purpose:'historical-context'}]}})
  expect(transport.readProductIndex.mock.calls[0][1]).toEqual({workId:null})
})

it('names the workspace at the application boundary without changing the professional title', () => {
  window.history.replaceState({},'', '/?workspace=enterprise&thread-fixture=idle-ieee39')
  const view=render(<App />)
  expect(document.title).toBe('Capstone · 企业工作台')
  view.unmount()
  window.history.replaceState({},'', '/?thread-fixture=idle-ieee39')
  render(<App />)
  expect(document.title).toBe('Capstone · 电网分析工作台')
})

it('opens the first newly delivered persisted result and does not reopen after the user closes it', async () => {
  const fixture=threadUiFixture('idle-ieee39')
  const context=(fixture.snapshot as {active_model_context:Record<string,unknown>}).active_model_context
  let deliver!:(event:EventEnvelope)=>void
  const transport={...createFixtureTransport(fixture), async *streamEvents(){while(true) yield await new Promise<EventEnvelope>(resolve=>{deliver=resolve})}}
  render(<ThreadFixtureApp client={new CapstoneThreadClient(transport)} threadId="thr_demo_39" presentation="workspace" navigation={<nav aria-label="任务会话" />} />)
  await screen.findByRole('textbox',{name:'Thread 指令'})
  await waitFor(()=>expect(deliver).toBeDefined())
  const emit=async(type:string,seq:number,payload:Record<string,unknown>)=>act(async()=>{deliver({eventId:`evt_${seq}`,eventSeq:seq,eventType:type,eventVersion:1,threadId:'thr_demo_39',runId:'run_001',turnId:'turn_new',attemptId:'attempt_new',modelContextId:String(context.id),occurredAt:'2026-10-17T01:00:00Z',visibility:'public',payload})})
  expect(screen.queryByRole('separator',{name:'调整对话与成果宽度'})).toBeNull()
  await emit('command_accepted',1,{kind:'send_auto',text:'检查当前模型'})
  expect(screen.getByRole('heading',{name:'电网分析与决策'})).toBeTruthy()
  await emit('attempt_started',2,{})
  const result={schema:'capstone-result-projection/1.0',result_id:'result_new',result_ref:`result:sha256:${'a'.repeat(64)}`,evidence_refs:[`evidence:sha256:${'b'.repeat(64)}`],thread_id:'thr_demo_39',run_id:'run_001',turn_id:'turn_new',attempt_id:'attempt_new',model_context_id:context.id,model_id:context.model_id,model_revision:context.model_revision,source:{capability_id:'powerflow.ac',domain_pack_id:'grid',implementation_family:'pandapower'},status:'completed',summary:[{metric_id:'loss',label:'有功损耗',value:1}],tables:[],element_refs:[]}
  await emit('attempt_completed',3,{answer:'已完成计算。',result_projections:[{...result,overlay:null,presentation:{collection_id:'analysis',collection_title:'电网分析结果',group_id:'state_1',group_title:'运行状态 1',purpose:'task_output'}}]})
  expect(await screen.findByRole('button',{name:'打开电网分析结果'})).toBeTruthy()
  expect(screen.getByRole('separator',{name:'调整对话与成果宽度'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'关闭电网分析结果'}))
  expect(screen.queryByRole('separator',{name:'调整对话与成果宽度'})).toBeNull()
  await emit('runtime_action',4,{})
  expect(screen.queryByRole('separator',{name:'调整对话与成果宽度'})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'打开电网分析结果'}))
  expect(screen.getByRole('region',{name:'结构化计算结果'})).toBeTruthy()
  const products=screen.getByRole('complementary',{name:'电网分析结果'})
  expect(products.querySelector('.workspace-product-stage')).toBeTruthy()
  expect(products.querySelector('.workspace-product-footer')).toBeTruthy()
  expect(screen.getByRole('tablist',{name:'成果视图'})).toBeTruthy()
  expect(screen.queryByRole('tab',{name:'报告'})).toBeNull()
})

it('restores conversation when the heading closes an expanded result view', async () => {
  render(<ThreadFixtureApp fixtureId="idle-ieee39" presentation="workspace" />)
  await screen.findByRole('textbox', {name:'Thread 指令'})
  fireEvent.click(screen.getByRole('button', {name:'打开电气拓扑'}))
  fireEvent.click(screen.getByRole('button', {name:'扩大成果区'}))
  expect(document.querySelector('.is-resource-expanded')).toBeTruthy()
  expect(screen.queryByRole('button', {name:/业务能力与资源/})).toBeNull()
  fireEvent.click(screen.getByRole('button', {name:'收起电气拓扑'}))
  expect(document.querySelector('.is-resource-expanded')).toBeNull()
  expect(screen.getByRole('textbox', {name:'Thread 指令'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button', {name:'打开电气拓扑'}))
  expect(screen.getByRole('button', {name:'扩大成果区'})).toBeTruthy()
})

it('presents the full conversation in the workspace with an optional real model region', async () => {
  render(<ThreadFixtureApp fixtureId="idle-ieee39" presentation="workspace"
    navigation={<nav id="thread-session-navigation" aria-label="任务会话"><button>新建会话</button></nav>} />)
  await screen.findByRole('textbox', {name:'Thread 指令'})
  const navigation=screen.getByRole('complementary',{name:'工作空间导航'})
  expect(navigation.querySelector('.workspace-brand')?.textContent).toContain('CAPSTONE')
  const main=document.querySelector('.workspace-shell')!
  const topbar=main.querySelector(':scope > .workspace-topbar')
  const titlebar=topbar?.querySelector(':scope > .workspace-workhead')
  const split=main.querySelector(':scope > .thread-app-columns')
  expect(topbar).toBeTruthy();expect(titlebar).toBeTruthy();expect(split).toBeTruthy()
  expect(titlebar?.contains(screen.getByRole('heading',{name:'电网分析与决策'}))).toBe(true)
  expect(screen.getByRole('region',{name:'Thread 对话区'}).contains(screen.getByRole('heading',{name:'电网分析与决策'}))).toBe(false)
  expect(screen.queryByRole('button',{name:/业务能力与资源/})).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'对话设置'}))
  expect(screen.getByRole('group',{name:'对话设置'})).toBeTruthy()
  fireEvent.keyDown(document,{key:'Escape'})
  expect(screen.getByRole('button', {name:'深度思考'})).toBeTruthy()
  expect(screen.getByRole('button', {name:'本轮上下文'})).toBeTruthy()
  expect(screen.getByRole('button', {name:'对话设置'})).toBeTruthy()
  expect(screen.queryByRole('button', {name:'保存任务'})).toBeNull()
  expect(screen.queryByRole('button', {name:'开始任务'})).toBeNull()
  expect(screen.queryByRole('region', {name:'电网模型区'})).toBeNull()
  const topology=screen.getByRole('button', {name:'打开电气拓扑'})
  expect(topology.textContent).toBe('拓扑')
  expect(topology.closest('.thread-model-short')?.textContent).toContain('pandapower')
  fireEvent.click(topology)
  expect(screen.getByRole('region', {name:'电网模型区'})).toBeTruthy()
  expect(screen.queryByRole('region',{name:'CAPSTONE 框架介绍'})).toBeNull()
  fireEvent.click(screen.getByRole('button', {name:'关闭电气拓扑'}))
  expect(screen.queryByRole('region', {name:'电网模型区'})).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button', {name:'打开电气拓扑'}))
})

it.each([false,true])('opens real delegated files without stealing restored history (restored=%s), and requires explicit adoption',async(restored)=>{
  vi.stubGlobal('URL',class extends URL {static createObjectURL=vi.fn(()=> 'blob:test-file');static revokeObjectURL=vi.fn()})
  const fixture=threadUiFixture('idle-ieee39')
  const context=(fixture.snapshot as {active_model_context:Record<string,unknown>}).active_model_context
  const digest='2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
  const artifact={schema:'capstone-process-artifact/1' as const,scope:'instruction' as const,thread_id:'thr_demo_39',run_id:'run_001',turn_id:'turn_new',attempt_id:'attempt_new',work_id:null,task_snapshot_id:null,goal_revision:null,task_id:'task_file',artifact_id:`file-${'a'.repeat(16)}-${digest}`,executor_identity_sha256:'b'.repeat(64),source_status:'completed',file_name:'analysis.txt',media_type:'text/plain',sha256:digest,size_bytes:5,download_url:`/api/v1/threads/thr_demo_39/attempts/attempt_new/artifacts/file-${'a'.repeat(16)}-${digest}`}
  if(restored){
    fixture.snapshot={...(fixture.snapshot as object),last_event_seq:2}
    fixture.events={schema:'capstone-thread-events/1',thread_id:'thr_demo_39',after_event_seq:0,next_event_seq:2,has_more:false,events:[
      {event_id:'evt_1',event_seq:1,event_type:'command_accepted',payload:{kind:'send_auto',text:'制作分析文件'}},
      {event_id:'evt_2',event_seq:2,event_type:'native_artifact_published',payload:{artifact}},
    ].map(event=>({...event,event_version:1,thread_id:'thr_demo_39',run_id:'run_001',turn_id:'turn_new',attempt_id:'attempt_new',model_context_id:context.id,occurred_at:'2026-10-17T01:00:00Z',visibility:'public'}))}
  }
  let deliver!:(event:EventEnvelope)=>void
  const publish=vi.fn()
  const transport={...createFixtureTransport(fixture),
    readNativeArtifacts:vi.fn(async()=>({artifacts:[artifact],hasMore:false,nextAfter:3})),
    readNativeArtifact:vi.fn(async()=>new TextEncoder().encode('hello')),
    readDeliveries:vi.fn(async()=>({schema:'capstone-deliveries/1',thread_id:'thr_demo_39',deliveries:[],has_more:false,next_before_event_seq:null})),
    publishDelivery:publish,readDeliveryContent:vi.fn(async()=>''),
    async *streamEvents(){while(true)yield await new Promise<EventEnvelope>(resolve=>{deliver=resolve})}}
  render(<ThreadFixtureApp client={new CapstoneThreadClient(transport)} threadId="thr_demo_39" presentation="workspace" />)
  await screen.findByRole('textbox',{name:'Thread 指令'})
  await waitFor(()=>expect(deliver).toBeDefined())
  const emit=async(type:string,seq:number,payload:Record<string,unknown>)=>act(async()=>{deliver({eventId:`evt_${seq}`,eventSeq:seq,eventType:type,eventVersion:1,threadId:'thr_demo_39',runId:'run_001',turnId:'turn_new',attemptId:'attempt_new',modelContextId:String(context.id),occurredAt:'2026-10-17T01:00:00Z',visibility:'public',payload})})
  if(restored){
    expect(screen.queryByRole('separator')).toBeNull()
    fireEvent.click(screen.getByRole('button',{name:'打开指令文件：analysis.txt'}))
  }else{
    await emit('command_accepted',1,{kind:'send_auto',text:'制作分析文件'})
    await emit('native_artifact_published',2,{artifact})
  }
  await screen.findByText('hello')
  expect(screen.getByRole('button',{name:'打开指令文件：analysis.txt'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'关闭指令文件'}))
  await emit('native_artifact_published',3,{artifact:{...artifact,file_name:'analysis-update.txt',artifact_id:artifact.artifact_id.replace('file-aaaaaaaaaaaaaaaa','file-bbbbbbbbbbbbbbbb'),download_url:artifact.download_url.replace('file-aaaaaaaaaaaaaaaa','file-bbbbbbbbbbbbbbbb')}})
  expect(screen.queryByRole('separator')).toBeNull()
  fireEvent.click(screen.getByRole('button',{name:'打开指令文件：analysis.txt'}))
  fireEvent.click(await screen.findByRole('button',{name:'作为任务交付'}))
  await screen.findByLabelText('交付名称')
  expect(screen.getByText(/采用已保存文件：analysis.txt/)).toBeTruthy()
  expect(publish).not.toHaveBeenCalled()
})
