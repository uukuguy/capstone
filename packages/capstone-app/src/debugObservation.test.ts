import {expect,it} from 'vitest'
import type {AttemptRecords} from './attemptRecords'
import {firstDebugObservation} from './debugObservation'

const record=(eventSeq:number,eventType:string,visibility='public')=>({eventSeq,eventType,visibility})
const page=(events:ReturnType<typeof record>[],nextAfter:number,hasMore:boolean)=>
  ({events,nextAfter,hasMore} as AttemptRecords)

it('locates the earliest visible failure across pages',async()=>{
  const read=async (_id:string,after=0)=>after===0?
    page([record(1,'tool_failed','diagnostic'),record(3,'tool_started')],3,true):
    page([record(5,'validation_failed'),record(6,'attempt_failed')],6,false)
  expect(await firstDebugObservation('a',read,6)).toEqual({seq:5,label:'核验失败'})
})

it('excludes later failures from the inspected snapshot',async()=>{
  const read=async()=>page([record(1,'tool_completed'),record(5,'attempt_interrupted')],5,false)
  expect(await firstDebugObservation('a',read,3)).toBeNull()
})

it('recognizes a failed validation observation even when the attempt completed',async()=>{
  const observation={...record(2,'validation_observation'),payload:{status:'failed'}}
  const read=async()=>page([observation,record(3,'attempt_completed')],3,false)
  expect(await firstDebugObservation('a',read,3)).toEqual({seq:2,label:'核验失败'})
})
