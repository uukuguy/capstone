import {fireEvent,render,screen,within} from '@testing-library/react'
import {expect,it,vi} from 'vitest'
import RequestContextEntries from './RequestContextEntries'
import {ThreadTransportError} from './threadHttpTransport'

it('loads the private index first, then its selected entry and the earlier index',async()=>{
  const entry={index:1,carrier:'system',role:'system',digest:'b'.repeat(64),source_id:'application-policy'}
  const index=(digest:string)=>({schema:'capstone-model-context-snapshot/1',total_entries:1,entries:[{...entry,digest}]})
  const read=vi.fn(async (_attempt:string,ref:string,i?:number,_signal?:AbortSignal,credential?:string)=>{
    if(!credential)throw new ThreadTransportError(403,'denied')
    return i===undefined?index(ref==='now'?'b'.repeat(64):'a'.repeat(64)):{entry:{...entry,text:'actual input'}}
  })
  const onCredential=vi.fn()
  render(<RequestContextEntries attempt="a" snapshot="now" previous="before" read={read}
    credential="operator-credential" onCredential={onCredential}/>)
  const panel=screen.getByRole('region',{name:'实际请求正文'})
  fireEvent.click(within(panel).getByRole('button',{name:'读取诊断记录'}))
  const row=await within(panel).findByRole('button',{name:'1 · 系统提示'})
  expect(within(panel).queryByText('actual input')).toBeNull()
  fireEvent.click(row)
  expect(await within(panel).findByText('actual input')).toBeTruthy()
  fireEvent.click(within(panel).getByRole('button',{name:'对比上一次请求'}))
  expect(await within(panel).findByText('改写 · 系统提示')).toBeTruthy()
  expect(read.mock.calls.map(call=>[call[1],call[2]])).toEqual([['now',undefined],['now',1],['before',undefined]])
})
