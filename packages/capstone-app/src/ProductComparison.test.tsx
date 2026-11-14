import {afterEach,expect,it,vi} from 'vitest'
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react'
import ProductComparison from './ProductComparison'
import {productRefKey,type ProductEntry} from './threadProducts'
afterEach(cleanup)
const ref={schema:'capstone-product-ref/1' as const,thread_id:'t',product_id:'a',origin:'native_file' as const,scope:'instruction' as const,event_seq:1,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:'a',producer_attempt_id:null}
const entry={ref,title:'same.md'} as ProductEntry
it('does not group duplicate titles and preserves the outside draft on failed comparison',async()=>{
 const other={...entry,ref:{...ref,product_id:'b'}}
 const client={discoverProductSeries:vi.fn().mockResolvedValue(null),productSources:vi.fn().mockResolvedValue([{ref,purpose:'historical-context'},{ref:other.ref,purpose:'historical-context'}]),compareProducts:vi.fn().mockRejectedValue(new Error('读取失败')),commandProductSeries:vi.fn(),seriesMembers:vi.fn()}
 render(<><textarea aria-label="草稿" defaultValue="保留内容"/><ProductComparison client={client} entry={entry} items={[entry,other]} onOpen={vi.fn()}/></>)
 expect(await screen.findByText('尚未登记系列')).toBeTruthy()
 expect(client.commandProductSeries).not.toHaveBeenCalled()
 expect(screen.getAllByRole('button',{name:/查看来源/})).toHaveLength(2)
 fireEvent.change(screen.getByLabelText('选择原稿'),{target:{value:productRefKey(other.ref)}})
 fireEvent.click(screen.getByRole('button',{name:'对照原稿与当前稿'}))
 expect((await screen.findByRole('alert')).textContent).toContain('读取失败')
 expect((screen.getByLabelText('草稿') as HTMLTextAreaElement).value).toBe('保留内容')
})
it('keeps a failed decision identity for retry, restores adoption on remount and clears explicitly',async()=>{
 let state={schema:'capstone-product-series/1' as const,thread_id:'t',series_id:'s',revision:1,members:[ref],adopted_ref:null as typeof ref|null}
 const client={discoverProductSeries:vi.fn(async()=>state),productSources:vi.fn().mockResolvedValue([]),compareProducts:vi.fn(),commandProductSeries:vi.fn().mockRejectedValueOnce(new Error('网络中断')).mockImplementation(async(_thread,command)=>{state={...state,revision:state.revision+1,adopted_ref:command.operation==='clear'?null:ref};return state}),seriesMembers:vi.fn(async()=>({members:state.members,next_cursor:null}))}
 const view=render(<ProductComparison client={client} entry={entry} items={[entry]} onOpen={vi.fn()}/>)
 fireEvent.click(await screen.findByRole('button',{name:'采用当前稿'}))
 expect((await screen.findByRole('alert')).textContent).toContain('网络中断')
 fireEvent.click(screen.getByRole('button',{name:'采用当前稿'}))
 await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('当前采用'))
 expect(client.commandProductSeries.mock.calls[0][1]).toEqual(client.commandProductSeries.mock.calls[1][1])
 view.unmount();render(<ProductComparison client={client} entry={entry} items={[entry]} onOpen={vi.fn()}/>)
 expect((await screen.findByRole('status')).textContent).toContain('当前采用')
 fireEvent.click(screen.getByRole('button',{name:'清除采用'}))
 await waitFor(()=>expect(screen.getByRole('status').textContent).toContain('尚未采用'))
})
it('refreshes a stale adoption state and supports keyboard-accessible explicit actions',async()=>{
 const state={schema:'capstone-product-series/1',thread_id:'t',series_id:'s',revision:1,members:[ref],adopted_ref:null}
 const client={discoverProductSeries:vi.fn().mockResolvedValue(state),productSources:vi.fn().mockResolvedValue([]),compareProducts:vi.fn(),commandProductSeries:vi.fn().mockRejectedValue(Object.assign(new Error('版本冲突'),{status:409})),seriesMembers:vi.fn().mockResolvedValue({members:[ref],next_cursor:null})}
 render(<ProductComparison client={client} entry={entry} items={[entry]} onOpen={vi.fn()}/>)
 const adopt=await screen.findByRole('button',{name:'采用当前稿'});adopt.focus();expect(document.activeElement).toBe(adopt)
 fireEvent.click(adopt)
 expect((await screen.findByRole('alert')).textContent).toContain('重新决定')
 expect(client.discoverProductSeries).toHaveBeenCalledTimes(2)
})
it('compares real original and revised text, then explicitly associates the new version',async()=>{
 const original={...entry,ref:{...ref,product_id:'original'}}
 const state={schema:'capstone-product-series/1',thread_id:'t',series_id:'original-series',revision:3,members:[original.ref],adopted_ref:null}
 const client={discoverProductSeries:vi.fn().mockResolvedValueOnce(null).mockResolvedValue(state),productSources:vi.fn().mockResolvedValue([]),compareProducts:vi.fn().mockResolvedValue({original_text:'原文🙂\r\n',revised_text:'改稿\n',changes:[{kind:'replace',original:[0,1],revised:[0,1]}]}),commandProductSeries:vi.fn().mockResolvedValue({...state,members:[original.ref,ref],revision:4}),seriesMembers:vi.fn()}
 render(<ProductComparison client={client} entry={entry} items={[entry,original]} onOpen={vi.fn()}/>)
 await screen.findByText('尚未登记系列')
 fireEvent.change(screen.getByLabelText('选择原稿'),{target:{value:productRefKey(original.ref)}})
 fireEvent.click(screen.getByRole('button',{name:'对照原稿与当前稿'}))
 expect((await screen.findByRole('region',{name:'原稿文字'})).textContent).toContain('原文🙂')
 expect(screen.getByRole('region',{name:'当前稿文字'}).textContent).toContain('改稿')
 expect(client.commandProductSeries).not.toHaveBeenCalled()
 fireEvent.click(screen.getByRole('button',{name:'明确关联到原稿系列'}))
 await waitFor(()=>expect(client.commandProductSeries).toHaveBeenCalledWith('t',expect.objectContaining({operation:'register',series_id:'original-series',expected_revision:3,product:ref})))
})
it('offers the exact series original by default and retries failed reads',async()=>{
 const original={...ref,product_id:'original'}
 const state={schema:'capstone-product-series/1',thread_id:'t',series_id:'s',revision:2,members:[original,ref],adopted_ref:null}
 const client={discoverProductSeries:vi.fn().mockRejectedValueOnce(new Error('读取中断')).mockResolvedValue(state),productSources:vi.fn().mockResolvedValue([]),seriesMembers:vi.fn().mockResolvedValue({members:[original,ref],next_cursor:null}),compareProducts:vi.fn(),commandProductSeries:vi.fn()}
 render(<ProductComparison client={client} entry={entry} items={[entry]} onOpen={vi.fn()}/>)
 await screen.findByRole('alert');fireEvent.click(screen.getByRole('button',{name:'重新读取系列'}))
 await waitFor(()=>expect((screen.getByLabelText('选择原稿') as HTMLSelectElement).value).toBe(productRefKey(original)))
})
