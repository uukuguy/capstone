import {expect,it} from 'vitest'
import {layoutSourceTopology} from './networkTopologyLayout'
it('uses source graph distances for bounded regional layout while keeping deterministic, separate records',()=>{
  const edges=new Uint32Array([0,1,1,2,2,0,2,3,3,4,4,5,5,3]),bounds={x:0,y:0,width:1000,height:1200}
  const first=layoutSourceTopology(7,edges,bounds),second=layoutSourceTopology(7,edges,bounds)
  expect([...first]).toEqual([...second])
  expect(new Set(Array.from({length:7},(_,i)=>`${first[i*2]}:${first[i*2+1]}`)).size).toBe(7)
  const distance=(a:number,b:number)=>Math.hypot(first[a*2]-first[b*2],first[a*2+1]-first[b*2+1])
  expect(distance(0,5)).toBeGreaterThan(distance(0,1))
  for(let i=0;i<7;i++){expect(first[i*2]).toBeGreaterThan(0);expect(first[i*2]).toBeLessThan(1000);expect(first[i*2+1]).toBeGreaterThan(0);expect(first[i*2+1]).toBeLessThan(1200)}
})
it('rejects an unbounded all-pairs job so large source scenes stay on the scalable worker path',()=>{
  expect(()=>layoutSourceTopology(120000,new Uint32Array(),{x:0,y:0,width:1000,height:600})).toThrow(/bounded/)
})
