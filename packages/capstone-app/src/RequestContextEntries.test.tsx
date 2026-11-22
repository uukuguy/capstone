import {cleanup,fireEvent,render,screen,within} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import RequestContextEntries from './RequestContextEntries'
import {ThreadTransportError} from './threadHttpTransport'

afterEach(cleanup)

it('loads the private index first, then its selected entry and the earlier index',async()=>{
  const entry={index:1,carrier:'system',role:'system',digest:'b'.repeat(64),source_id:'application-policy'}
  const index=(digest:string)=>({schema:'capstone-model-context-snapshot/1',total_entries:1,entries:[{...entry,digest}]})
  const read=vi.fn(async (_attempt:string,ref:string,i?:number)=>{
    return i===undefined?index(ref==='now'?'b'.repeat(64):'a'.repeat(64)):{entry:{...entry,text:'actual input'}}
  })
  render(<RequestContextEntries attempt="a" snapshot="now" previous="before" category="system" read={read}/>)
  const panel=screen.getByRole('region',{name:'实际请求正文'})
  const row=await within(panel).findByRole('button',{name:'1 系统提示'})
  expect(within(panel).queryByText('actual input')).toBeNull()
  fireEvent.click(row)
  expect(await within(panel).findByText('actual input')).toBeTruthy()
  fireEvent.click(within(panel).getByRole('button',{name:'对比上一请求'}))
  expect(await within(panel).findByRole('button',{name:'改写 · 系统提示'})).toBeTruthy()
  expect(within(panel).getByText('actual input')).toBeTruthy()
  fireEvent.click(row)
  expect(within(panel).queryByText('actual input')).toBeNull()
  expect(read.mock.calls.map(call=>[call[1],call[2]])).toEqual([['now',undefined],['now',1],['before',undefined]])
})

it('keeps access errors in the inspector without requesting a credential',async()=>{
  const read=vi.fn(async()=>{throw new ThreadTransportError(403,'denied')})
  render(<RequestContextEntries attempt="a" snapshot="locked" read={read}/>)
  await screen.findByText(/当前入口无法查看受保护正文/)
  expect(read).toHaveBeenCalledTimes(1)
  expect(screen.queryByRole('textbox')).toBeNull()
})

it('presents runtime and handoff sources as expandable request rows',async()=>{
  const entries=[{index:1,carrier:'messages',role:'user',origin:{kind:'runtime',id:'execution-state',revision:'admitted',delivery:'text'}},
    {index:2,carrier:'messages',role:'user',origin:{kind:'handoff',id:'selected-task-handoff',revision:'admitted',delivery:'text'}}]
  const read=vi.fn(async (_attempt:string,_ref:string,index?:number)=>index===undefined
    ? {schema:'capstone-model-context-snapshot/1',total_entries:entries.length,entries}
    : {entry:{index,text:'admitted handoff body'}})
  render(<RequestContextEntries attempt="a" snapshot="now" read={read}/>)
  await screen.findByRole('button',{name:/1 运行环境/})
  fireEvent.click(screen.getByRole('button',{name:/2 任务交接/}))
  expect(await screen.findByText('admitted handoff body')).toBeTruthy()
  expect(read.mock.calls.map(call=>call[2])).toEqual([undefined,2])
  expect(screen.queryByLabelText('按来源筛选')).toBeNull()
})

it('formats and highlights JSON while preserving the captured values',async()=>{
  const entry={index:1,carrier:'tools',role:'definition',name:'example'}
  const raw='{"id":9007199254740993,"options":[true,null,"a\\n"],"id":-1.5e2}'
  const read=vi.fn(async (_attempt:string,_ref:string,index?:number)=>index===undefined
    ? {schema:'capstone-model-context-snapshot/1',total_entries:1,entries:[entry]}
    : {entry:{index,text:raw}})
  const {container}=render(<RequestContextEntries attempt="a" snapshot="now" category="tools" read={read}/>)
  fireEvent.click(await screen.findByRole('button',{name:'1 example'}))
  const json=await screen.findByLabelText('JSON 正文')
  expect(json.textContent).toBe('{\n  "id": 9007199254740993,\n  "options": [\n    true,\n    null,\n    "a\\n"\n  ],\n  "id": -1.5e2\n}')
  expect(container.querySelectorAll('.context-json-key')).toHaveLength(3)
  expect(container.querySelector('.context-json-number')?.textContent).toBe('9007199254740993')
})

it('reads the correct bodies only when a comparison item opens',async()=>{
  const system={carrier:'system',role:'system',source_id:'system-policy'}
  const rows={
    before:[{...system,index:8,digest:'a'.repeat(64)},{index:9,carrier:'tools',role:'definition',name:'retired'}],
    now:[{...system,index:3,digest:'b'.repeat(64)},{index:4,carrier:'tools',role:'definition',name:'added'}],
  }
  const texts:Record<string,string>={'before:8':'old policy','now:3':'new policy','before:9':'old tool','now:4':'new tool'}
  const read=vi.fn(async (_attempt:string,ref:string,index?:number)=>index===undefined
    ? {schema:'capstone-model-context-snapshot/1',total_entries:2,entries:rows[ref as keyof typeof rows]}
    : {entry:{index,text:texts[`${ref}:${index}`]}})
  render(<RequestContextEntries attempt="a" snapshot="now" previous="before" read={read}/>)
  fireEvent.click(await screen.findByRole('button',{name:'对比上一请求'}))
  fireEvent.click(await screen.findByRole('button',{name:'改写 · 系统提示'}))
  expect(await screen.findByText('old policy')).toBeTruthy()
  expect(await screen.findByText('new policy')).toBeTruthy()
  fireEvent.click(await screen.findByRole('button',{name:/移除.*retired/}))
  expect(await screen.findByText('old tool')).toBeTruthy()
  fireEvent.click(await screen.findByRole('button',{name:/新增.*added/}))
  expect(await screen.findByText('new tool')).toBeTruthy()
  expect(read.mock.calls.map(call=>[call[1],call[2]])).toEqual([
    ['now',undefined],['before',undefined],['before',8],['now',3],['before',9],['now',4],
  ])
})

it('shows every captured entry in order while loading bodies on demand',async()=>{
  const entries=Array.from({length:22},(_,i)=>({index:i+1,carrier:'messages',role:'user'}))
  const read=vi.fn(async()=>({schema:'capstone-model-context-snapshot/1',total_entries:entries.length,entries}))
  render(<RequestContextEntries attempt="a" snapshot="now" read={read}/>)
  expect(await screen.findByRole('button',{name:'22 用户消息'})).toBeTruthy()
  expect(screen.getAllByRole('button').map(button=>button.getAttribute('aria-label'))).toEqual(
    entries.map(entry=>`${entry.index} 用户消息`))
  expect(read).toHaveBeenCalledTimes(1)
})

it('keeps request groups separate and uses recorded message boundaries',async()=>{
  const entries=[
    {index:1,carrier:'system',role:'system'},
    {index:2,carrier:'tools',role:'definition',name:'read'},
    {index:3,carrier:'messages',role:'assistant',message_index:1,block_index:1,preview:'I will read the file.'},
    {index:4,carrier:'messages',role:'toolCall',message_index:1,block_index:2,name:'read'},
    {index:5,carrier:'tool_results',role:'toolResult',message_index:2,block_index:1,name:'read'},
  ]
  const read=vi.fn(async()=>({schema:'capstone-model-context-snapshot/1',total_entries:entries.length,entries}))
  const {container}=render(<RequestContextEntries attempt="a" snapshot="now" read={read}/>)
  await screen.findByText('I will read the file.')
  expect([...container.querySelectorAll('details.context-input-group')].every(group=>!group.hasAttribute('open'))).toBe(true)
  expect([...container.querySelectorAll('.context-input-message')].map(group=>group.querySelectorAll('ol > li').length)).toEqual([2,1])
  expect(read).toHaveBeenCalledTimes(1)
})
