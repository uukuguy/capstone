import {describe,it,expect} from 'vitest'
import {parseResourceReadPage,parseResourceRead} from './resourceReads'
import {initializeApplicationCapacity} from './applicationCapacity'
export const receipt={schema:'capstone-resource-read/1',read_id:'read_'+'a'.repeat(32),thread_id:'thr_one',attempt_id:'att_one',task_id:'task_one',request_id:'req_one',resource:{schema:'capstone-resource/1',resource_id:'resource_'+'b'.repeat(32),thread_id:'thr_one',version:1,file_name:'input.txt',size_bytes:100,sha256:'c'.repeat(64)},offset:10,length:4,sha256:'d'.repeat(64),preview:{bytes_read:4,truncated:false,status:'text',text:'data'}}
describe('resource read contracts',()=>{
 it('rejects ambiguous text byte counts and malformed Unicode',()=>{
  for(const text of ['abc','abcde','\ud800abc','\udc00abc'])expect(()=>parseResourceRead({...receipt,preview:{...receipt.preview,text}},'thr_one','att_one')).toThrow()
  expect(parseResourceRead({...receipt,preview:{...receipt.preview,text:'😀'}},'thr_one','att_one').preview.text).toBe('😀')
 })
 it('rejects extra resource fields',()=>{
  for(const extra of [{private_path:'/private'},{object_key:'secret'}])expect(()=>parseResourceRead({...receipt,resource:{...receipt.resource,...extra}},'thr_one','att_one')).toThrow()
 })
 it('uses the selected preview budget',()=>{
  try{initializeApplicationCapacity({resource_read_preview_bytes:3});expect(()=>parseResourceRead(receipt,'thr_one','att_one')).toThrow()}finally{initializeApplicationCapacity()}
  try{
   initializeApplicationCapacity({resource_read_preview_bytes:9000})
   const larger={...receipt,resource:{...receipt.resource,size_bytes:10000},length:9000,preview:{...receipt.preview,bytes_read:9000,text:'a'.repeat(9000)}}
   expect(parseResourceRead(larger,'thr_one','att_one').preview.bytes_read).toBe(9000)
  }finally{initializeApplicationCapacity()}
 })
 it('checks strict scoped cursors before accepting a page',()=>{
  const page={schema:'capstone-resource-read-page/1',items:[],next_cursor:null}
  const cursor=(value:unknown)=>btoa(JSON.stringify(value)).replaceAll('+','-').replaceAll('/','_')
  const valid={thread:'thr_one',attempt:'att_one',after:3}
  expect(parseResourceReadPage({...page,next_cursor:cursor(valid)},'thr_one','att_one').next_cursor).toBe(cursor(valid))
  for(const next_cursor of ['!', 'a'.repeat(1025),cursor({...valid,thread:'thr_other'}),cursor({...valid,attempt:'att_other'}),cursor({...valid,after:-1}),cursor({...valid,after:1.5}),cursor({...valid,after:true}),cursor({...valid,after:Number.MAX_SAFE_INTEGER+1}),cursor({...valid,extra:1})])expect(()=>parseResourceReadPage({...page,next_cursor},'thr_one','att_one')).toThrow()
 })
 it('retains exact source identity and range',()=>{expect(parseResourceRead(receipt,'thr_one','att_one')).toEqual(receipt)})
 it('rejects ownership, bounds and malformed pages',()=>{
 for(const patch of [{thread_id:'thr_other'},{attempt_id:'att_other'},{offset:-1},{length:101},{offset:1.5},{private_path:'/private'}])expect(()=>parseResourceRead({...receipt,...patch},'thr_one','att_one')).toThrow()
 for(const patch of [{next_cursor:5},{items:[{...receipt,thread_id:'thr_other'}]},{schema:'other'}])expect(()=>parseResourceReadPage({schema:'capstone-resource-read-page/1',items:[receipt],next_cursor:null,...patch},'thr_one','att_one')).toThrow()
 })
})
