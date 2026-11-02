import {useEffect,useState} from 'react'
import {Plus} from 'lucide-react'
import WorkspaceSessionEntry from './WorkspaceSessionEntry'
import {navigateSession} from './SessionNavigation'
import './sessionEntry.css'

/** Keep the current conversation and draft mounted until creation succeeds. */
export default function SessionNewPopover({onCreated}:{onCreated?:(id:string)=>void}) {
  const [creating,setCreating]=useState(false)
  useEffect(()=>{
    const cancel=()=>setCreating(false)
    window.addEventListener('popstate',cancel)
    return()=>window.removeEventListener('popstate',cancel)
  },[])
  return <><button type="button" className="thread-session-new" disabled={creating} aria-busy={creating} onClick={()=>setCreating(true)}><Plus size={16} aria-hidden="true"/>新建会话</button>
    {creating&&<WorkspaceSessionEntry compact onCreated={id=>{setCreating(false);(onCreated??navigateSession)(id)}}/>}
  </>
}
