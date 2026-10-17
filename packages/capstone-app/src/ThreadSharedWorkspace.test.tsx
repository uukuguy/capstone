import { afterEach, expect, it } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import ThreadFixtureApp from './ThreadFixtureApp'
import { CapstoneThreadClient } from './threadClient'
import { createFixtureTransport } from './threadProjectionStore'
import { threadUiFixture } from './threadUiFixtures'
import type { EventEnvelope } from './threadProtocol'
import App from './App'

afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); window.history.replaceState({},'', '/') })

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
  expect(screen.queryByRole('separator')).toBeNull()
  await emit('command_accepted',1,{kind:'send_auto',text:'检查当前模型'})
  expect(screen.getByRole('heading',{name:'检查当前模型'})).toBeTruthy()
  await emit('attempt_started',2,{})
  const result={schema:'capstone-result-projection/1.0',result_id:'result_new',result_ref:`result:sha256:${'a'.repeat(64)}`,evidence_refs:[`evidence:sha256:${'b'.repeat(64)}`],thread_id:'thr_demo_39',run_id:'run_001',turn_id:'turn_new',attempt_id:'attempt_new',model_context_id:context.id,model_id:context.model_id,model_revision:context.model_revision,source:{capability_id:'powerflow.ac',domain_pack_id:'grid',implementation_family:'pandapower'},status:'completed',summary:[{metric_id:'loss',label:'有功损耗',value:1}],tables:[],element_refs:[]}
  await emit('attempt_completed',3,{answer:'已完成计算。',result_projections:[{...result,overlay:null,presentation:{collection_id:'analysis',collection_title:'电网分析结果',group_id:'state_1',group_title:'运行状态 1',purpose:'task_output'}}]})
  expect(await screen.findByRole('button',{name:'打开电网分析结果'})).toBeTruthy()
  expect(screen.getByRole('separator')).toBeTruthy()
  fireEvent.click(screen.getByRole('button',{name:'关闭电网分析结果'}))
  expect(screen.queryByRole('separator')).toBeNull()
  await emit('runtime_action',4,{})
  expect(screen.queryByRole('separator')).toBeNull()
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
  fireEvent.click(screen.getByRole('button', {name:'查看模型与结果'}))
  fireEvent.click(screen.getByRole('button', {name:'扩大成果区'}))
  expect(document.querySelector('.is-resource-expanded')).toBeTruthy()
  expect(screen.queryByRole('button', {name:/业务能力与资源/})).toBeNull()
  fireEvent.click(screen.getByRole('button', {name:'查看模型与结果'}))
  expect(document.querySelector('.is-resource-expanded')).toBeNull()
  expect(screen.getByRole('textbox', {name:'Thread 指令'})).toBeTruthy()
  fireEvent.click(screen.getByRole('button', {name:'查看模型与结果'}))
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
  const titlebar=main.querySelector(':scope > .workspace-workhead')
  const split=main.querySelector(':scope > .thread-app-columns')
  expect(topbar).toBeTruthy();expect(titlebar).toBeTruthy();expect(split).toBeTruthy()
  expect(titlebar?.contains(screen.getByRole('heading',{name:'新会话'}))).toBe(true)
  expect(screen.getByRole('region',{name:'Thread 对话区'}).contains(screen.getByRole('heading',{name:'新会话'}))).toBe(false)
  fireEvent.click(screen.getByRole('button',{name:/业务能力与资源/}))
  expect(screen.getByRole('group',{name:'对话设置'})).toBeTruthy()
  fireEvent.keyDown(document,{key:'Escape'})
  expect(screen.getByRole('button', {name:'选择技能'})).toBeTruthy()
  expect(screen.getByRole('button', {name:'本轮上下文'})).toBeTruthy()
  expect(screen.getByRole('button', {name:'对话设置'})).toBeTruthy()
  expect(screen.queryByRole('button', {name:'保存任务'})).toBeNull()
  expect(screen.queryByRole('button', {name:'开始任务'})).toBeNull()
  expect(screen.queryByRole('region', {name:'电网模型区'})).toBeNull()
  fireEvent.click(screen.getByRole('button', {name:'查看模型与结果'}))
  expect(screen.getByRole('region', {name:'电网模型区'})).toBeTruthy()
  expect(screen.queryByRole('region',{name:'CAPSTONE 框架介绍'})).toBeNull()
  fireEvent.click(screen.getByRole('button', {name:'关闭模型与结果'}))
  expect(screen.queryByRole('region', {name:'电网模型区'})).toBeNull()
  expect(document.activeElement).toBe(screen.getByRole('button', {name:'查看模型与结果'}))
})
