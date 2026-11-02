import {initializeApplicationCapacity,readRuntimeCapacity} from './applicationCapacity'
import {fetchWithReadRetry} from './httpRetry'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'
import './styles-light.css'

declare global {interface Window {__CAPSTONE_CAPACITY__?:unknown}}
const root=ReactDOM.createRoot(document.getElementById('root')!)
async function start(){
  root.render(<main role="status">正在读取应用配置…</main>)
  try{
    if(window.__CAPSTONE_CAPACITY__!==undefined)initializeApplicationCapacity(window.__CAPSTONE_CAPACITY__)
    // Offline fixtures keep their deterministic initialization without an API dependency.
    if(!new URLSearchParams(window.location.search).has('thread-fixture'))await readRuntimeCapacity(import.meta.env.VITE_API_ORIGIN||'',undefined,(url,init)=>fetchWithReadRetry(String(url),init))
    root.render(<React.StrictMode><App /></React.StrictMode>)
  }catch(error){root.render(<main role="alert"><p>{error instanceof Error?error.message:'应用容量配置无效。'}</p><button onClick={()=>void start()}>重新读取配置</button></main>)}
}
void start()
