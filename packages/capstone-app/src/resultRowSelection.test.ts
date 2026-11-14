import {expect,it} from 'vitest'
import {parseContextProductRefs,productSelectionKey,type ProductRef} from './threadProducts'
import {parseRowPage} from './resultRowSelection'
export const ref:ProductRef={schema:'capstone-product-ref/1',thread_id:'thr_one',product_id:'result_one',origin:'domain_result',scope:'instruction',event_seq:1,revision:null,digest:'a'.repeat(64),work_id:null,attempt_id:'att_one',producer_attempt_id:null}
const selection={schema:'capstone-result-row-selection/1',parent_ref:ref,table_id:'table_one',table_version:'b'.repeat(64),row_ids:['r1'],column_ids:['value'],digest:'c'.repeat(64)}
it('preserves distinct row material keys and rejects mixed scopes and forged parents',()=>{
 const a={ref,purpose:'historical-context',row_selection:selection}
 const b={...a,row_selection:{...selection,row_ids:['r2']}}
 const parsed=parseContextProductRefs([a,b]);expect(productSelectionKey(parsed[0])).not.toBe(productSelectionKey(parsed[1]))
 for(const row of [{...selection,parent_ref:{...ref,event_seq:2}},{...selection,row_ids:['r1','r1']},{...selection,row_ids:['r2','r1']},{...selection,digest:'bad'}])expect(()=>parseContextProductRefs([{...a,row_selection:row}])).toThrow()
 expect(()=>parseContextProductRefs([{...a,excerpt:{max_bytes:1}}])).toThrow()
})
it('rejects forged page identities and nonadvancing offsets',()=>{
 const page={schema:'capstone-result-row-page/1',parent_ref:ref,table_version:'b'.repeat(64),table:{table_id:'table_one',title:'结果',columns:[{column_id:'value',label:'值',unit:'MW'}],rows:[{row_id:'r1',cells:{value:null}}]},total_rows:2,offset:0,next_offset:1}
 expect(parseRowPage(page,ref,'table_one',0).table.rows[0].cells.value).toBeNull()
 for(const p of [{...page,next_offset:0},{...page,parent_ref:{...ref,digest:'d'.repeat(64)}},{...page,table:{...page.table,rows:[...page.table.rows,...page.table.rows]}}])expect(()=>parseRowPage(p,ref,'table_one',0)).toThrow()
})
