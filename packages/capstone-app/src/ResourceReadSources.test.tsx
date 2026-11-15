import {it,expect,vi,afterEach} from 'vitest'
import {render,screen,fireEvent,cleanup,waitFor} from '@testing-library/react'
import ResourceReadSources from './ResourceReadSources'
const receipt={schema:'capstone-resource-read/1',read_id:'read_'+'a'.repeat(32),thread_id:'thr_one',attempt_id:'att_one',task_id:'task_one',request_id:'req_one',resource:{schema:'capstone-resource/1',resource_id:'resource_'+'b'.repeat(32),thread_id:'thr_one',version:1,file_name:'input.txt',size_bytes:100,sha256:'c'.repeat(64)},offset:10,length:4,sha256:'d'.repeat(64),preview:{bytes_read:4,truncated:false,status:'text',text:'data'}}
afterEach(cleanup)
it('shows exact partial range and opens preview only on action',async()=>{
 const client={listResourceReads:vi.fn().mockResolvedValue({items:[receipt],next_cursor:null}),readResourceRead:vi.fn().mockResolvedValue(receipt)}
 render(<ResourceReadSources client={client} threadId="thr_one" attemptId="att_one" revision={1}/> )
 expect(await screen.findByText('input.txt · v1')).toBeTruthy()
 expect(screen.getByText(/10–13/)).toBeTruthy();expect(screen.getByText(/部分覆盖/)).toBeTruthy()
 expect(screen.getByText(/此回执仅覆盖上述范围；其他范围请查看其他回执/)).toBeTruthy()
 expect(screen.queryByText(/此回执以外的字节未读取/)).toBeNull()
 expect(client.readResourceRead).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'查看有界预览'}))
 expect(await screen.findByText('data')).toBeTruthy()
})
it('discards late response after thread switch and distinguishes failure from empty',async()=>{
 let resolve!:(v:unknown)=>void
 const client={listResourceReads:vi.fn().mockImplementationOnce(()=>new Promise(r=>resolve=r)).mockResolvedValue({items:[],next_cursor:null})}
 const view=render(<ResourceReadSources client={client} threadId="thr_one" attemptId="att_one" revision={1}/> )
 view.rerender(<ResourceReadSources client={client} threadId="thr_two" attemptId="att_two" revision={1}/> )
 await screen.findByText('此执行没有已确认的资源范围读取。')
 resolve({items:[receipt],next_cursor:null});await waitFor(()=>expect(screen.queryByText('input.txt · v1')).toBeNull())
 client.listResourceReads.mockRejectedValue(new Error('读取失败'))
 view.rerender(<ResourceReadSources client={client} threadId="thr_two" attemptId="att_two" revision={2}/> )
 expect(await screen.findByRole('alert')).toBeTruthy()
})
