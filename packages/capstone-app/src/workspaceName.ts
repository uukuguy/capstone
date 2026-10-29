export const defaultWorkspaceName='enterprise'
export function normalizeWorkspaceName(value:string){
  if(/[\p{Cc}\p{Cf}\p{Cs}]/u.test(value))throw new Error('工作空间名称无效')
  const name=value.trim().normalize('NFC')
  if(!name||Array.from(name).length>128||new TextEncoder().encode(name).byteLength>512)throw new Error('工作空间名称需为 1—128 个字符')
  return name
}
export function currentWorkspaceName(){return normalizeWorkspaceName(new URLSearchParams(window.location.search).get('workspace')??defaultWorkspaceName)}
export function isWorkspaceActive(name:string){try{return currentWorkspaceName()===name}catch{return false}}
export function workspaceThreadUrl(id:string){const url=new URL(window.location.href);url.searchParams.set('workspace',currentWorkspaceName());url.searchParams.set('thread',id);url.searchParams.delete('thread-fixture');return url.pathname+url.search+url.hash}
