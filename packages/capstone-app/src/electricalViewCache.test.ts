import {expect,it} from 'vitest'
import {createIndexedDBElectricalViewStore,electricalCacheIdentity,initialElectricalCheckpoint,validateElectricalCachedPage,validateElectricalCheckpoint} from './electricalViewCache'
import {electricalOverviewManifest,electricalOverviewRecords,electricalPage} from './electricalModelFixtures'

/** Minimal asynchronous IDB test driver. Read/write transactions serialize and
 * publish their private snapshot only on complete; abort discards every write. */
function indexedDBDriver(){
  let data=new Map<string,Map<string,unknown>>(),busy=false,upgraded=false
  const queue:(()=>void)[]=[]
  const db={
    close(){},onversionchange:null,
    createObjectStore(name:string){data.set(name,new Map())},
    transaction(names:string[]){
      let snapshot:typeof data,pending=0,started=false,done=false,completion:ReturnType<typeof setTimeout>|undefined
      const work:(()=>void)[]=[]
      const next=()=>{busy=false;queue.shift()?.()}
      const finish=()=>{if(started&&pending===0&&!done){clearTimeout(completion);completion=setTimeout(()=>{if(done)return;done=true;data=snapshot;tx.oncomplete?.();next()},0)}}
      const tx={error:null as DOMException|null,oncomplete:null as null|(()=>void),onabort:null as null|(()=>void),onerror:null,
        abort(){if(done)throw new DOMException('Inactive','InvalidStateError');done=true;clearTimeout(completion);setTimeout(()=>{tx.onabort?.();next()},0)},
        objectStore(name:string){
          if(!names.includes(name))throw Error('unknown store')
          const operation=(kind:'get'|'add'|'put',key:IDBValidKey,value?:unknown)=>{
            const req={onsuccess:null as null|(()=>void),onerror:null as null|(()=>void),result:undefined as unknown,error:null as DOMException|null}
            pending++;clearTimeout(completion)
            const execute=()=>setTimeout(()=>{
              if(done)return
              const store=snapshot.get(name)!,encoded=JSON.stringify(key)
              if(kind==='add'&&store.has(encoded)){req.error=tx.error=new DOMException('Duplicate','ConstraintError');req.onerror?.();tx.abort();return}
              if(kind==='get')req.result=structuredClone(store.get(encoded))
              else {store.set(encoded,structuredClone(value));req.result=key}
              pending--;req.onsuccess?.();finish()
            },0)
            if(started)execute();else work.push(execute)
            return req
          }
          return {get:(key:IDBValidKey)=>operation('get',key),add:(value:unknown,key:IDBValidKey)=>operation('add',key,value),put:(value:unknown,key:IDBValidKey)=>operation('put',key,value)}
        },
      }
      const begin=()=>{busy=true;started=true;snapshot=structuredClone(data);work.forEach(run=>run());finish()}
      if(busy)queue.push(begin);else begin()
      return tx
    },
  }
  const factory={open(){const req={result:db,onupgradeneeded:null as null|(()=>void),onsuccess:null as null|(()=>void),onerror:null,onblocked:null};setTimeout(()=>{if(!upgraded){upgraded=true;req.onupgradeneeded?.()}req.onsuccess?.()},0);return req}}
  return factory as unknown as IDBFactory
}

it('persists records and checkpoints atomically; duplicate page abort retains the previous cursor',async()=>{
  const records=electricalOverviewRecords();records.devices=[{id:'d0',kind:'breaker'},{id:'d1',kind:'breaker'},{id:'d2',kind:'breaker'}]
  const manifest=electricalOverviewManifest(records),factory=indexedDBDriver(),store=createIndexedDBElectricalViewStore({indexedDB:factory})
  const before=(await store.initialize(manifest)).devices!
  const first=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices',limit:1})
  const after=await store.commitPage(manifest,'devices',before,first)
  expect(after.loaded).toBe(1)
  const duplicate=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices',cursor:after.cursor!,limit:2})
  duplicate.records[1]={id:'d0',kind:'breaker'} as never
  await expect(store.commitPage(manifest,'devices',after,duplicate)).rejects.toThrow('duplicate_record')
  expect(await store.getRecord(manifest.view_ref,'devices','d1')).toBeUndefined()
  expect((await store.initialize(manifest)).devices).toEqual(after)
  const valid=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices',cursor:after.cursor!,limit:2})
  const final=await store.commitPage(manifest,'devices',after,valid)
  expect(final.complete).toBe(true);expect(await store.getRecord(manifest.view_ref,'devices','d2')).toMatchObject({id:'d2'})
  store.close?.()
  const restored=createIndexedDBElectricalViewStore({indexedDB:factory})
  expect((await restored.initialize(manifest)).devices).toEqual(final)
  expect(await restored.getRecord(manifest.view_ref,'devices','d0')).toMatchObject({id:'d0'})
  await expect(restored.commitPage(manifest,'devices',before,first)).rejects.toThrow('cache_checkpoint_conflict')
})

it('rejects a non-adjacent cursor cycle transactionally without retaining page records',async()=>{
  const records=electricalOverviewRecords();records.devices=Array.from({length:4},(_,i)=>({id:`d${i}`,kind:'breaker'}))
  const manifest=electricalOverviewManifest(records),store=createIndexedDBElectricalViewStore({indexedDB:indexedDBDriver()})
  let checkpoint=(await store.initialize(manifest)).devices!
  for(let i=0;i<2;i++)checkpoint=await store.commitPage(manifest,'devices',checkpoint,electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices',cursor:checkpoint.cursor??undefined,limit:1}))
  const cycle=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices',cursor:checkpoint.cursor!,limit:1});cycle.next_cursor='cursor:devices:1'
  await expect(store.commitPage(manifest,'devices',checkpoint,cycle)).rejects.toThrow('cursor_cycle')
  expect(await store.getRecord(manifest.view_ref,'devices','d2')).toBeUndefined()
  expect((await store.initialize(manifest)).devices).toEqual(checkpoint)
})

it('keeps existing pages on quota exhaustion and refuses manifest identity reuse',async()=>{
  const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
  const page=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices',limit:500})
  const store=createIndexedDBElectricalViewStore({indexedDB:indexedDBDriver(),maxBytes:1})
  const checkpoint=(await store.initialize(manifest)).devices!
  await expect(store.commitPage(manifest,'devices',checkpoint,page)).rejects.toThrow('cache_quota_exceeded')
  expect((await store.initialize(manifest)).devices).toEqual(checkpoint)
  const changed=structuredClone(manifest);changed.model_revision='changed'
  await expect(store.initialize(changed)).rejects.toThrow('cache_identity_mismatch')
})

it('rejects obsolete checkpoints, malformed pages and summary streams before storage',()=>{
  const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records),checkpoint=initialElectricalCheckpoint(manifest,'devices')
  const page=electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices',limit:500})
  expect(()=>validateElectricalCheckpoint(manifest,'devices',{...checkpoint,version:2} as never)).toThrow('cache_checkpoint_invalid')
  expect(()=>validateElectricalCachedPage(manifest,'devices',checkpoint,{...page,selection_ref:'other'})).toThrow('frozen_baseline_mismatch')
  expect(()=>initialElectricalCheckpoint(manifest,'summary_nodes')).toThrow('cache_detail_stream_required')
  const changed=structuredClone(manifest);changed.streams.ports.total_count++
  expect(electricalCacheIdentity(changed)).not.toBe(electricalCacheIdentity(manifest))
})

it('does not fabricate cache completion when IndexedDB is unavailable or a transaction is cancelled',async()=>{
  const records=electricalOverviewRecords(),manifest=electricalOverviewManifest(records)
  const unavailable=createIndexedDBElectricalViewStore({indexedDB:{} as IDBFactory})
  await expect(unavailable.initialize(manifest)).rejects.toBeTruthy()
  const store=createIndexedDBElectricalViewStore({indexedDB:indexedDBDriver()}),checkpoint=(await store.initialize(manifest)).devices!
  const abort=new AbortController();abort.abort()
  await expect(store.commitPage(manifest,'devices',checkpoint,electricalPage(manifest,records,{view_ref:manifest.view_ref,stream:'devices'}),abort.signal)).rejects.toMatchObject({name:'AbortError'})
  expect((await store.initialize(manifest)).devices).toEqual(checkpoint)
})
