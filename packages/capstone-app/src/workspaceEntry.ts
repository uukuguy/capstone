import {currentWorkspaceName} from './workspaceName'
const key=(workspace=currentWorkspaceName())=>`capstone.workspace.last-thread:${encodeURIComponent(import.meta.env.VITE_API_ORIGIN||window.location.origin)}${workspace==='enterprise'?'':`:workspace:${encodeURIComponent(workspace)}`}`
export function readLastWorkspaceThread(workspace?:string):string|undefined {
  try{const value=localStorage.getItem(key(workspace));return value&&/^[a-z][a-z0-9_-]{0,63}$/.test(value)?value:undefined}catch{return undefined}
}
export function rememberWorkspaceThread(id:string){if(!/^[a-z][a-z0-9_-]{0,63}$/.test(id)||id==='new')return;try{localStorage.setItem(key(),id)}catch{/* Navigation still works. */}}
export function forgetWorkspaceThread(id?:string,workspace?:string){try{if(!id||readLastWorkspaceThread(workspace)===id)localStorage.removeItem(key(workspace))}catch{/* Navigation still works. */}}
export type WorkspacePanels={navigation?:boolean;resource?:boolean}
const panelsKey=(id:string)=>`${key()}:panels:${id}`
export function readWorkspacePanels(id?:string):WorkspacePanels {if(!id)return {};try{const value=JSON.parse(localStorage.getItem(panelsKey(id))||'{}');return {navigation:typeof value?.navigation==='boolean'?value.navigation:undefined,resource:typeof value?.resource==='boolean'?value.resource:undefined}}catch{return {}}}
export function saveWorkspacePanels(id:string|undefined,value:WorkspacePanels){if(!id)return;try{localStorage.setItem(panelsKey(id),JSON.stringify({...readWorkspacePanels(id),...value}))}catch{/* Keep live state. */}}
