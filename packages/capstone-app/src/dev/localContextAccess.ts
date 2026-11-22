import type {IncomingMessage} from 'node:http'

const loopbackHosts=new Set(['localhost','127.0.0.1','[::1]'])
const loopbackPeers=new Set(['127.0.0.1','::1','::ffff:127.0.0.1'])
const identifier='[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}'
const snapshotRoute=new RegExp(`^/api/v1/threads/${identifier}/attempts/${identifier}/context-snapshots/ctxdoc_[a-f0-9]{32}(?:\\?index=[1-9][0-9]{0,2})?$`)

export function isLocalContextRead(request:IncomingMessage,target:string):boolean {
  const {headers,method,socket,url}=request
  if(method!=='GET'||!url||!snapshotRoute.test(url)||headers.authorization||
    !socket.remoteAddress||!loopbackPeers.has(socket.remoteAddress)||headers['sec-fetch-site']!=='same-origin'||
    // Make the authorization decision at the directly connected browser hop.
    Object.keys(headers).some(name=>name==='forwarded'||name.startsWith('x-forwarded-')))return false

  const allowedAuthorities=[...loopbackHosts].map(host=>`${host}:${socket.localPort}`)
  if(!headers.host||!allowedAuthorities.includes(headers.host))return false
  if(headers.origin!==undefined&&headers.origin!==`http://${headers.host}`)return false

  try{
    const upstream=new URL(target)
    return upstream.protocol==='http:'&&loopbackHosts.has(upstream.hostname)&&
      upstream.pathname==='/'&&!upstream.search&&!upstream.hash&&!upstream.username&&!upstream.password
  }catch{return false}
}
