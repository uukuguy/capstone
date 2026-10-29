import {afterEach,expect,it} from 'vitest'
import {cleanup,fireEvent,render,screen} from '@testing-library/react'
import RequestPoolQueue,{RequestPoolExecutions} from './RequestPoolQueue'
import type {ProcessModelRequest} from './processModelRequestPool'
afterEach(cleanup)
const queued:ProcessModelRequest={id:'request-1',chainId:'main',kind:'main',modelTurnNumber:1,title:'LLM 1',dependsOn:[],status:'queued',queuedAtMs:100}
it('places queued/dependency and not-yet-dispatched semantic work in the pending queue only',()=>{
 const view=render(<RequestPoolQueue requests={[queued,{...queued,id:'request-2',status:'waiting_dependencies',dependsOn:['request-1']}]} jobs={[{id:'job',parentToolCallId:'submit',title:'等待分析',status:'queued',queuedAtMs:100,responseCount:0}]}/>)
 expect(screen.getByLabelText('模型请求等待队列')).toBeTruthy();expect(screen.getByText('等待分析')).toBeTruthy();expect(screen.getByText(/等待依赖/)).toBeTruthy()
 view.rerender(<RequestPoolQueue requests={[{...queued,status:'running',startedAtMs:800}]} jobs={[]}/> )
 expect(screen.queryByLabelText('模型请求等待队列')).toBeNull()
})
it('expands actual running requests, preserves manual disclosure and labels uncertain cleanup',()=>{
 const running={...queued,status:'running' as const,startedAtMs:800}
 const view=render(<RequestPoolExecutions requests={[running]} active now={900}/>)
 const detail=document.querySelector('details')!;expect(detail.open).toBe(true)
 fireEvent.click(detail.querySelector('summary')!);expect(detail.open).toBe(false)
 view.rerender(<RequestPoolExecutions requests={[{...running,status:'cancelling'}]} active now={1000}/>)
 expect(detail.open).toBe(false);expect(screen.getByText('取消中 · 等待释放')).toBeTruthy()
})
