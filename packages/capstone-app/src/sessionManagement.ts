import {HttpThreadTransport} from './threadHttpTransport'
import {commandKey} from './commandKey'
import {parseCommandReceipt} from './threadProtocol'
import type {ThreadListPage} from './threadManagement'
import {forgetWorkspaceThread} from './workspaceEntry'
import {storageNamespace} from './threadSessionState'
import {restoreCatalogSession,removeCatalogSession} from './sessionCatalog'

export type SessionManagementActions={rename:(id:string,text:string)=>Promise<void>;archive:(id:string,value:boolean)=>Promise<void>;remove:(id:string)=>Promise<void>;archived:(before?:string)=>Promise<ThreadListPage>;history?:(archived:boolean,signal:AbortSignal)=>Promise<ThreadListPage['threads']>}
export async function readSessionHistory(transport:Pick<HttpThreadTransport,'listThreads'>,archived:boolean,signal:AbortSignal){
  const records=new Map<string,ThreadListPage['threads'][number]>(),cursors=new Set<string>()
  let before:string|undefined
  while(!signal.aborted){
    const page=await transport.listThreads(archived,before,signal)
    if(signal.aborted)throw new Error('读取已取消')
    page.threads.forEach(item=>records.set(item.threadId,item))
    if(!page.hasMore)return [...records.values()]
    const next=page.nextBeforeThreadId
    if(!next||cursors.has(next))throw new Error('会话目录未完整读取')
    cursors.add(next);before=next
  }
  throw new Error('读取已取消')
}
export function sessionManagement(transport:HttpThreadTransport,onChanged:(change?:{remove:string})=>void):SessionManagementActions {
  return {
    async rename(id,text){
      const snapshot=await transport.getSessionManagementSnapshot(id)
      const key=commandKey(),receipt=parseCommandReceipt(await transport.renameSession(id,snapshot.run.run_id,snapshot.session_title?.revision??0,text,`cmd_${key}`,`idem_${key}`))
      if(receipt.status!=='accepted')throw new Error('名称未保存，请重试。')
      onChanged();window.dispatchEvent(new Event('capstone-session-renamed'))
    },
    async archive(id,value){const thread=await transport.archiveThread(id,value),namespace=storageNamespace(import.meta.env.VITE_API_ORIGIN||'');if(value){removeCatalogSession(namespace,id);forgetWorkspaceThread(id);window.dispatchEvent(new CustomEvent('capstone-session-released',{detail:id}))}else restoreCatalogSession(namespace,thread);onChanged(value?{remove:id}:undefined)},
    async remove(id){await transport.deleteThread(id);removeCatalogSession(storageNamespace(import.meta.env.VITE_API_ORIGIN||''),id);forgetWorkspaceThread(id);window.dispatchEvent(new CustomEvent('capstone-session-released',{detail:id}));onChanged({remove:id})},
    archived:before=>transport.listThreads(true,before),
    history:(archived,signal)=>readSessionHistory(transport,archived,signal),
  }
}
