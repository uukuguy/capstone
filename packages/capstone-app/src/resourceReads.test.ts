import {describe,it,expect} from 'vitest'
import {parseResourceReadPage,parseResourceRead} from './resourceReads'
export const receipt={schema:'capstone-resource-read/1',read_id:'read_'+'a'.repeat(32),thread_id:'thr_one',attempt_id:'att_one',task_id:'task_one',request_id:'req_one',resource:{schema:'capstone-resource/1',resource_id:'resource_'+'b'.repeat(32),thread_id:'thr_one',version:1,file_name:'input.txt',size_bytes:100,sha256:'c'.repeat(64),processing_state:'stored'},offset:10,length:4,sha256:'d'.repeat(64),preview:{bytes_read:4,truncated:false,status:'text',text:'data'}}
describe('resource read contracts',()=>{
 it('retains exact source identity and range',()=>{expect(parseResourceRead(receipt,'thr_one','att_one')).toEqual(receipt)})
 it('rejects ownership, bounds and malformed pages',()=>{
 for(const patch of [{thread_id:'thr_other'},{attempt_id:'att_other'},{offset:-1},{length:101},{offset:1.5},{private_path:'/private'}])expect(()=>parseResourceRead({...receipt,...patch},'thr_one','att_one')).toThrow()
 for(const patch of [{next_cursor:5},{items:[{...receipt,thread_id:'thr_other'}]},{schema:'other'}])expect(()=>parseResourceReadPage({schema:'capstone-resource-read-page/1',items:[receipt],next_cursor:null,...patch},'thr_one','att_one')).toThrow()
 })
})
