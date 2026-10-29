import {afterEach,expect,it,vi} from 'vitest'
import {currentWorkspaceName,normalizeWorkspaceName,workspaceThreadUrl} from './workspaceName'
import {storageNamespace} from './threadSessionState'
import {HttpThreadTransport} from './threadHttpTransport'
import {sessionManagement} from './sessionManagement'
afterEach(()=>window.history.replaceState({},'','/'))
it('normalizes named URLs and preserves their space in thread links and caches',()=>{
  window.history.replaceState({},'','/?workspace='+encodeURIComponent(' 华北研究 '))
  expect(currentWorkspaceName()).toBe('华北研究')
  expect(new URL(workspaceThreadUrl('thr_a'),window.location.origin).searchParams.get('workspace')).toBe('华北研究')
  const a=storageNamespace('')
  window.history.replaceState({},'','/?workspace=B');expect(storageNamespace('')).not.toBe(a)
  expect(()=>normalizeWorkspaceName('x\n')).toThrow()
})
it('freezes the workspace into requests even when the browser later switches spaces',async()=>{
  window.history.replaceState({},'','/?workspace='+encodeURIComponent('华北研究'))
  const fetcher=vi.fn<typeof fetch>().mockResolvedValue(new Response('{}',{headers:{'Capstone-Thread-Version':'2','Capstone-Workspace':encodeURIComponent('华北研究')}}))
  const transport=new HttpThreadTransport('','',fetcher,'/api/v1/threads','2')
  window.history.replaceState({},'','/?workspace=B')
  await transport.getSnapshot('thr_a')
  expect(new Headers(fetcher.mock.calls[0][1]?.headers).get('Capstone-Workspace')).toBe(encodeURIComponent('华北研究'))
})
it('rejects a named-space response from an older server that ignored its workspace header',async()=>{
  const fetcher=vi.fn<typeof fetch>().mockResolvedValue(new Response('{}',{headers:{'Capstone-Thread-Version':'2'}}))
  const transport=new HttpThreadTransport('','',fetcher,'/api/v1/threads','2','B')
  await expect(transport.getSnapshot('thr_a')).rejects.toThrow('尚未确认')
})
it('retains workspace scope through mixed-version list fallback',async()=>{
  const page={schema:'capstone-thread-list/1',threads:[],has_more:false,next_before_thread_id:null}
  const fetcher=vi.fn<typeof fetch>().mockResolvedValueOnce(new Response(JSON.stringify({error:'protocol_upgrade_required'}),{status:409})).mockResolvedValueOnce(new Response(JSON.stringify(page),{headers:{'Capstone-Thread-Version':'2','Capstone-Workspace':'A'}}))
  const transport=new HttpThreadTransport('','',fetcher,'/api/v1/threads','1','A')
  window.history.replaceState({},'','/?workspace=B')
  await transport.listThreads()
  expect(fetcher.mock.calls.every(call=>new Headers(call[1]?.headers).get('Capstone-Workspace')==='A')).toBe(true)
})
it('keeps a delayed archive restoration in its original catalog after the URL changes',async()=>{
  window.history.replaceState({},'','/?workspace=A')
  const namespace=storageNamespace(''),changed=vi.fn(),events:string[]=[]
  const listener=(event:Event)=>events.push((event as CustomEvent<string>).detail)
  window.addEventListener('capstone-session-catalog-changed',listener)
  let finish!:(value:unknown)=>void
  const transport={workspaceName:'A',archiveThread:vi.fn(()=>new Promise(resolve=>{finish=resolve}))} as unknown as HttpThreadTransport
  const pending=sessionManagement(transport,changed).archive('thr_a',false)
  window.history.replaceState({},'','/?workspace=B')
  finish({threadId:'thr_a',modelId:null,implementationFamily:null,createdAt:'2026-10-29',archived:false,lastEventSeq:0})
  await pending
  expect(events.at(-1)).toBe(namespace);expect(changed).not.toHaveBeenCalled()
  window.removeEventListener('capstone-session-catalog-changed',listener)
})
