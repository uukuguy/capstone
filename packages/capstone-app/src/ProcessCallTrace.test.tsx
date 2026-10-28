import { afterEach, expect, it } from 'vitest'
import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import ProcessCallTrace, { callTraceIssues } from './ProcessCallTrace'

afterEach(cleanup)
it('uses compact glyphs and outlines actual parallel tools without repeated status text',()=>{
  render(<ProcessCallTrace compact models={[{id:'m',number:1,ms:1200,toolCallIds:['a','b']}]} tools={[
    {id:'a',name:'Read A',status:'completed',startedAt:'2026-10-29T00:00:00Z',durationMs:500},
    {id:'b',name:'Read B',status:'completed',startedAt:'2026-10-29T00:00:00.100Z',durationMs:200},
  ]}/>)
  expect(screen.getByRole('img',{name:'已返回'})).toBeTruthy()
  expect(screen.getAllByRole('img',{name:'完成'})).toHaveLength(2)
  expect(screen.getByText('LLM 01')).toBeTruthy()
  expect(screen.queryByText('已返回')).toBeNull()
  expect(screen.queryByText('并行调用')).toBeNull()
  expect(screen.getByRole('group',{name:'并行工具调用 · 2 项'})).toBeTruthy()
})

it('grades model and tool latency separately and updates a live request grade',()=>{
  const models=[{id:'m',number:1,ms:0,startedAt:'2026-10-29T00:00:00Z',toolCallIds:['t']}]
  const tools=[{id:'t',name:'Query',status:'completed' as const,durationMs:6000}]
  const view=render(<ProcessCallTrace models={models} tools={tools} now={Date.parse('2026-10-29T00:00:12Z')}/>)
  expect(screen.getByText('12.0s')).toHaveAttribute('data-latency','noticeable')
  expect(within(screen.getByText('Query').closest('summary')!).getByText('6.0s')).toHaveAttribute('data-latency','slow')
  view.rerender(<ProcessCallTrace models={models} tools={tools} now={Date.parse('2026-10-29T00:01:01Z')}/>)
  expect(screen.getByText('61.0s')).toHaveAttribute('data-latency','very-slow')
  expect(screen.getByText('61.0s').getAttribute('title')).toContain('明显偏长')
})

it('keeps tool cancellation distinct from a tool failure',()=>{
  render(<ProcessCallTrace models={[{id:'m',number:1,ms:100,toolCallIds:['cancelled']}]} tools={[{id:'cancelled',name:'Stopped query',status:'cancelled',durationMs:100}]}/>)
  expect(screen.getByText('已停止')).toBeVisible()
  expect(screen.queryByText('失败')).toBeNull()
})

it('marks overlapping tools only inside the same response and keeps each tool collapsed',()=>{
  render(<ProcessCallTrace models={[{id:'m1',number:1,ms:100,toolCallIds:['a','b']},{id:'m2',number:2,ms:100,toolCallIds:['c']}]} tools={[
    {id:'a',name:'read A',status:'completed',startedAt:'2026-10-29T00:00:00Z',durationMs:500},
    {id:'b',name:'read B',status:'completed',startedAt:'2026-10-29T00:00:00.100Z',durationMs:200},
    {id:'c',name:'read C',status:'completed',startedAt:'2026-10-29T00:00:00.100Z',durationMs:200},
  ]}/>)
  expect(within(screen.getByRole('group',{name:'LLM 调用 1'})).getAllByText('并行调用')).toHaveLength(2)
  expect(within(screen.getByRole('group',{name:'LLM 调用 2'})).queryByText('并行调用')).toBeNull()
  expect(screen.getByText('read A').closest('details')).not.toHaveAttribute('open')
  expect(within(screen.getByText('read A').closest('summary')!).getByText('500ms')).toBeVisible()
})

it('explains a classified model failure without exposing unknown error text',()=>{
  render(<ProcessCallTrace models={[{id:'error',number:1,ms:100,stopReason:'error',errorCode:'model_context_limit',errorStatus:400},
    {id:'unknown',number:2,ms:100,stopReason:'error',errorCode:'private-provider-text'}]} tools={[]} />)
  expect(screen.getByText('上下文超限 · HTTP 400')).toBeVisible()
  expect(screen.queryByText('private-provider-text')).toBeNull()
})

it('shows the actual shell action instead of its workspace prefix and retains the full command', () => {
  const operation = 'cd /var/lib/general-pi/tasks/private-workspace && python3 analyze_prices.py --monthly'
  render(<ProcessCallTrace models={[{id:'m',number:1,ms:100,toolCallIds:[],toolRequests:[{id:'t',name:'bash',operation}]}]} tools={[]} />)
  const intent = screen.getByText('发起工具：bash · python3 analyze_prices.py --monthly')
  expect(intent).toHaveAttribute('title', `bash · ${operation}`)
})

it('uses a leading script comment as the action summary without an added label', () => {
  const operation = "cd '/private/task workspace' && python3 - <<'PY'\n# 计算各省月度负电价频次，保存汇总表\nimport pandas as pd\nprint('done')\nPY"
  render(<ProcessCallTrace models={[{id:'m',number:1,ms:100,toolCallIds:[],toolRequests:[{id:'t',name:'bash',operation}]}]} tools={[]} />)
  expect(screen.getByText('发起工具：bash · 计算各省月度负电价频次，保存汇总表')).toHaveAttribute('title', `bash · ${operation}`)
})

it('keeps zero-tool responses and nests only exact declared tool IDs', () => {
  render(<ProcessCallTrace models={[
    { id: 'm1', number: 1, ms: 500, toolCallIds: ['a', 'b'] },
    { id: 'm2', number: 2, ms: 200, toolCallIds: [] },
    { id: 'm3', number: 3, ms: 300, toolCallIds: ['c'] },
  ]} tools={[
    { id: 'c', name: 'write', status: 'completed' },
    { id: 'b', name: 'read B', status: 'completed' },
    { id: 'a', name: 'read A', status: 'completed' },
    { id: 'orphan', name: 'legacy tool', status: 'completed' },
    { id: 'host', name: '保存产物', status: 'completed', origin: 'system' },
  ]} />)
  const first=screen.getByRole('group', { name: 'LLM 调用 1' })
  expect(within(first).getByText('read A')).toBeVisible()
  expect(within(first).getByText('read B')).toBeVisible()
  expect(within(first).queryByText('write')).toBeNull()
  expect(within(screen.getByRole('group', { name: 'LLM 调用 2' })).getByText('未调用工具')).toBeVisible()
  expect(within(screen.getByRole('group', { name: 'LLM 调用 3' })).getByText('write')).toBeVisible()
  expect(screen.getByText('未关联')).toBeVisible()
  expect(screen.getByText('系统动作')).toBeVisible()
})

it('does not infer historical tool ownership from adjacent timestamps', () => {
  render(<ProcessCallTrace models={[{ id:'old',number:1,ms:100,finishedAt:'2026-10-24T00:00:01Z' }]}
    tools={[{ id:'old-tool',name:'read',status:'completed',startedAt:'2026-10-24T00:00:02Z' }]} />)
  expect(within(screen.getByRole('group',{name:'LLM 调用 1'})).queryByText('read')).toBeNull()
  expect(screen.getByText('工具关联未记录')).toBeVisible()
  expect(screen.getByText('未关联')).toBeVisible()
})

it('updates an active request duration and stops claiming live execution at termination', () => {
  const models=[{id:'live',number:1,ms:0,startedAt:'2026-10-24T00:00:00Z'}]
  const view=render(<ProcessCallTrace models={models} tools={[]} now={Date.parse('2026-10-24T00:00:02Z')} />)
  expect(screen.getByText('2.0s')).toBeVisible()
  expect(screen.getByText('进行中')).toBeVisible()
  view.rerender(<ProcessCallTrace models={models} tools={[]} now={Date.parse('2026-10-24T00:00:04Z')} />)
  expect(screen.getByText('4.0s')).toBeVisible()
  view.rerender(<ProcessCallTrace models={models} tools={[]} active={false} />)
  expect(screen.queryByText('进行中')).toBeNull()
  expect(screen.getByText('未完整记录')).toBeVisible()
})

it('does not attach a tool claimed by more than one response', () => {
  render(<ProcessCallTrace models={[
    {id:'m1',number:1,ms:1,toolCallIds:['ambiguous']},
    {id:'m2',number:2,ms:1,toolCallIds:['ambiguous']},
  ]} tools={[{id:'ambiguous',name:'read',status:'completed'}]} />)
  for(const n of [1,2])expect(within(screen.getByRole('group',{name:`LLM 调用 ${n}`})).queryByText('read')).toBeNull()
  expect(screen.getByText('未关联')).toBeVisible()
})

it('flags only settled missing records and shows concise call purpose and token information', () => {
  const models=[{id:'m1',number:1,ms:1200,toolCallIds:['missing'],toolRequests:[{id:'missing',name:'write',operation:'report.md'}],
    responseText:'整理已有结论，写入报告。',usage:{input:80,cacheRead:20,cacheWrite:0,output:12}}]
  expect(callTraceIssues(models,[],true)).toEqual([])
  expect(callTraceIssues(models,[],false)).toMatchObject([{modelId:'m1',number:1,missingToolIds:['missing']}])
  expect(callTraceIssues([...models,{id:'m2',number:2,ms:0,startedAt:'2026-10-24T00:00:01Z'}],[],true)).toHaveLength(1)
  render(<ProcessCallTrace models={models} tools={[]} active={false} />)
  expect(screen.getByText('工具记录缺失 · 1项')).toBeVisible()
  expect(screen.getByText(/输入 100/)).toBeVisible()
  expect(screen.getByText(/输出 12/)).toBeVisible()
  expect(screen.getByText(/write.*report.md/)).toBeVisible()
  expect(screen.getByText('整理已有结论，写入报告。')).toBeVisible()
})
