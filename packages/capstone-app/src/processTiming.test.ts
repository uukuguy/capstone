import {expect,it} from 'vitest'
import {batchElapsedMs} from './processTiming'

const at=(ms:number)=>new Date(ms).toISOString()
it('measures the whole batch envelope including gaps rather than summing tools',()=>{
 expect(batchElapsedMs([
  {startedAt:at(0),finishedAt:at(100),status:'completed'},
  {startedAt:at(200),finishedAt:at(300),status:'completed'},
 ])).toBe(300)
 expect(batchElapsedMs([
  {startedAt:at(0),finishedAt:at(100),status:'completed'},
  {startedAt:at(50),finishedAt:at(150),status:'completed'},
 ])).toBe(150)
})
it('updates a running batch and keeps missing or unfinished history unknown',()=>{
 const calls=[{startedAt:at(0),finishedAt:at(100),status:'completed'},{startedAt:at(200),status:'running'}]
 expect(batchElapsedMs(calls,true,350)).toBe(350)
 expect(batchElapsedMs(calls,false,350)).toBeUndefined()
 expect(batchElapsedMs([{status:'completed',durationMs:3}])).toBeUndefined()
 expect(batchElapsedMs([{startedAt:at(200),finishedAt:at(100),status:'completed'}])).toBeUndefined()
})
