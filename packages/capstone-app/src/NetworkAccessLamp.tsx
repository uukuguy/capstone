import {applicationCapacity} from './applicationCapacity'
import { useEffect, useRef, useState } from 'react'
import './networkAccessLamp.css'

export default function NetworkAccessLamp({fetcher=fetch}: {fetcher?:typeof fetch}) {
  const [enabled,setEnabled]=useState<boolean|null>(null)
  const [pending,setPending]=useState(false)
  const [error,setError]=useState('')
  const [showError,setShowError]=useState(false)
  const busy=useRef(false)
  const generation=useRef(0)
  const mounted=useRef(true)
  async function request(next?:boolean) {
    let token=''
    try { token=sessionStorage.getItem('capstone.thread.operatorToken') || '' } catch { /* Open workbench. */ }
    const response=await fetcher(`${import.meta.env.VITE_API_ORIGIN || ''}/api/v1/network-policy`,{
      method:next===undefined?'GET':'POST',credentials:'omit',cache:'no-store',
      headers:{...(token?{Authorization:`Bearer ${token}`} : {}),...(next===undefined?{}:{'Content-Type':'application/json'})},
      ...(next===undefined?{}:{body:JSON.stringify({external_access:next})}),
      signal:AbortSignal.timeout(applicationCapacity('ui_network_status_timeout_ms')),
    })
    if(!response.ok)throw new Error('network state unavailable')
    const state=await response.json()
    if(state.enforced!==true || typeof state.external_access!=='boolean')throw new Error('unconfirmed network state')
    return state.external_access as boolean
  }
  async function refresh() {
    if(busy.current)return
    const id=++generation.current
    try {const value=await request();if(mounted.current&&id===generation.current){setEnabled(value);setError('')}}
    catch {if(mounted.current&&id===generation.current){setEnabled(null);setError('外网状态暂不可用，点击重试')}}
  }
  useEffect(()=>{
    mounted.current=true
    void refresh()
    const timer=window.setInterval(()=>void refresh(),applicationCapacity('ui_network_status_refresh_ms'))
    const focus=()=>void refresh()
    window.addEventListener('focus',focus)
    return ()=>{mounted.current=false;++generation.current;clearInterval(timer);window.removeEventListener('focus',focus)}
  },[fetcher])
  async function toggle() {
    if(busy.current)return
    if(enabled===null){void refresh();return}
    busy.current=true;++generation.current;setPending(true);setError('');setShowError(false)
    try {const value=await request(!enabled);if(mounted.current)setEnabled(value)}
    catch {
      // A response can be lost after the change. Re-read before displaying it.
      try {const value=await request();if(mounted.current)setEnabled(value)}
      catch {if(mounted.current)setEnabled(null)}
      if(mounted.current){setError('切换未确认，请重试');setShowError(true)}
    } finally {busy.current=false;if(mounted.current)setPending(false)}
  }
  const label=pending?'正在切换外网访问':error || (enabled===null?'正在读取外网状态':`外网已${enabled?'开启':'关闭'} · 点击${enabled?'关闭':'开启'}`)
  return <span className="network-access-control">
    <button type="button" role="switch" aria-checked={enabled===true} aria-busy={pending}
      aria-label={label} title={`全局外网访问：${label}。获准内网工具及模型服务连接独立管理。`}
      className="network-access-lamp" data-state={enabled===null?'unknown':enabled?'on':'off'}
      disabled={pending} onClick={()=>void toggle()}><span aria-hidden="true" /></button>
    {showError && error && <span className="network-access-error" role="status">{error}</span>}
  </span>
}
