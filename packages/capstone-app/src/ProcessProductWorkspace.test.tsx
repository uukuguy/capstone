import {afterEach,it,expect,vi} from 'vitest'
import {cleanup,render,screen,fireEvent,waitFor} from '@testing-library/react'
import ProcessProductWorkspace from './ProcessProductWorkspace'
import type {CapstoneThreadClient} from './threadClient'
import type {ProcessProduct} from './processProducts'

afterEach(cleanup)
const product:ProcessProduct={productId:'process_attempt_1',threadId:'thr_1',attemptId:'attempt_1',workId:null,instruction:'检查过载',status:'failed',eventSeq:9,occurredAt:'2026-10-17T00:00:00Z',failureCode:null,modelContext:null}
it('shows failure, locates and explicitly references the original attempt without fabricating output',async()=>{
  const client={processProducts:vi.fn().mockResolvedValue({products:[product],hasMore:false,nextBefore:1}),attemptRecords:vi.fn().mockResolvedValue({threadId:'thr_1',attemptId:'attempt_1',events:[],hasMore:false,nextAfter:0})} as unknown as CapstoneThreadClient
  const locate=vi.fn(),reference=vi.fn()
  render(<ProcessProductWorkspace client={client} threadId="thr_1" revision={9} onLocate={locate} onReference={reference} />)
  await screen.findByText('未完成')
  fireEvent.click(screen.getByRole('button',{name:'定位指令'}));expect(locate).toHaveBeenCalledWith('attempt_1')
  fireEvent.click(screen.getByRole('button',{name:'引用到下一轮'}));expect(reference).toHaveBeenCalledWith(product)
  fireEvent.click(screen.getByRole('button',{name:'查看结果'}))
  await screen.findByText('本次指令没有已保存的结构化结果，可定位原指令查看回答。')
  expect(screen.queryByText('计算结果')).toBeNull()
})
it('skips bounded empty event pages and retains the cursor for more history',async()=>{
  const read=vi.fn().mockResolvedValueOnce({products:[],hasMore:true,nextBefore:20}).mockResolvedValueOnce({products:[product],hasMore:true,nextBefore:10}).mockResolvedValue({products:[],hasMore:false,nextBefore:1})
  const client={processProducts:read} as unknown as CapstoneThreadClient
  render(<ProcessProductWorkspace client={client} threadId="thr_1" revision={9} onLocate={()=>{}} onReference={()=>{}} />)
  await screen.findByText('检查过载')
  expect(read.mock.calls[1][1]).toBe(20)
  fireEvent.click(screen.getByRole('button',{name:'更早的指令'}))
  await waitFor(()=>expect(read).toHaveBeenCalledTimes(3))
  expect(read.mock.calls[2][1]).toBe(10)
  expect(screen.getByText('检查过载')).toBeTruthy()
})
