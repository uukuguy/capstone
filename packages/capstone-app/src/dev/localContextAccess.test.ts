import type {IncomingMessage} from 'node:http'
import {expect,it} from 'vitest'
import {isLocalContextRead} from './localContextAccess'

const target='http://127.0.0.1:8767'
const request={
  method:'GET',url:'/api/v1/threads/thr_1/attempts/attempt_2/context-snapshots/ctxdoc_0123456789abcdef0123456789abcdef?index=1',
  headers:{host:'127.0.0.1:5173','sec-fetch-site':'same-origin'},
  socket:{remoteAddress:'127.0.0.1',localPort:5173},
}
function allowed(patch:Record<string,unknown>={},destination=target){
  return isLocalContextRead({...request,...patch} as unknown as IncomingMessage,destination)
}
it('authorizes only a same-origin loopback diagnostic read to a local backend',()=>{
  expect(allowed()).toBe(true)
  expect(allowed({socket:{...request.socket,remoteAddress:'192.168.1.9'}})).toBe(false)
  expect(allowed({headers:{...request.headers,host:'example.test:5173'}})).toBe(false)
  expect(allowed({headers:{...request.headers,'sec-fetch-site':'cross-site'}})).toBe(false)
  expect(allowed({headers:{...request.headers,origin:'https://example.test'}})).toBe(false)
  expect(allowed({headers:{...request.headers,'x-forwarded-for':'127.0.0.1'}})).toBe(false)
  expect(allowed({method:'POST'})).toBe(false)
  expect(allowed({url:'/api/v1/threads/thr_1/events'})).toBe(false)
  expect(allowed({},'https://example.test')).toBe(false)
})
