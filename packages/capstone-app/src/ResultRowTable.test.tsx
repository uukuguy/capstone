import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react'
import {afterEach,expect,it,vi} from 'vitest'
import ResultRowTable from './ResultRowTable'
import type {ResultProjection,ResultTable} from './threadProtocol'
import type {ProductRef} from './threadProducts'
afterEach(cleanup)
const ref:ProductRef={schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'result_one',origin:'domain_result',scope:'instruction',event_seq:1,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:'att_one',producer_attempt_id:null}
const table:ResultTable={tableId:'table_one',title:'线路',columns:[{columnId:'value',label:'功率',unit:'MW'}],rows:[{rowId:'r1',cells:{value:0}},{rowId:'r2',cells:{value:0}}],pagination:{manifestRef:`table-manifest:sha256:${'a'.repeat(64)}`,totalRows:3,pageSize:2}}
it('keeps repeated-value row identities across sorting filtering and page changes',async()=>{
 const onSelect=vi.fn(),readResultRows=vi.fn(async(_ref,_table,offset=0)=>({table:offset?{...table,rows:[{rowId:'r3',cells:{value:null}}]}:table,tableVersion:'b'.repeat(64),offset,totalRows:3,nextOffset:offset?null:2})),prepareResultRows=vi.fn(async(_ref,_table,rows,columns)=>({schema:'capstone-result-row-selection/1' as const,parent_ref:ref,table_id:'table_one',table_version:'b'.repeat(64),row_ids:[...rows].sort(),column_ids:columns,digest:'c'.repeat(64)}))
 render(<><input aria-label="草稿" defaultValue="保留问题"/><ResultRowTable table={table} projection={{} as ResultProjection} selection={{ref,client:{readResultRows,prepareResultRows},onSelect}}/></>)
 await waitFor(()=>expect((screen.getByLabelText('选择行 r1') as HTMLInputElement).disabled).toBe(false))
 fireEvent.click(screen.getByLabelText('选择行 r2'))
 fireEvent.change(screen.getByLabelText('排序 线路'),{target:{value:'value'}})
 fireEvent.change(screen.getByLabelText('筛选 线路'),{target:{value:'missing'}})
 expect(screen.queryByLabelText('选择行 r2')).toBeNull()
 fireEvent.change(screen.getByLabelText('筛选 线路'),{target:{value:''}})
 expect((screen.getByLabelText('选择行 r2') as HTMLInputElement).checked).toBe(true)
 fireEvent.click(screen.getByRole('button',{name:'下一页'}))
 await screen.findByLabelText('选择行 r3');fireEvent.click(screen.getByLabelText('选择行 r3'))
 fireEvent.click(screen.getByRole('button',{name:'引用所选行到下一轮'}))
 await waitFor(()=>expect(onSelect).toHaveBeenCalled())
 expect(prepareResultRows).toHaveBeenCalledWith(ref,'table_one',['r2','r3'],['value'])
 expect((screen.getByLabelText('草稿') as HTMLInputElement).value).toBe('保留问题')
})
