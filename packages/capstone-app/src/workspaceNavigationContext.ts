import {createContext,useContext,type RefObject} from 'react'
import type {GatewayConnectionStatus} from './threadInput'
import type {ThreadListPage} from './threadManagement'

export type WorkspaceNavigationState={
  enterprise?:boolean
  open:boolean
  toggle:()=>void
  panelId:string
  toggleRef:RefObject<HTMLButtonElement|null>
  gateway:GatewayConnectionStatus|undefined
  catalog:ThreadListPage|null
  refreshCatalog:()=>void
}
export const WorkspaceNavigationContext=createContext<WorkspaceNavigationState|null>(null)
export const useWorkspaceNavigation=()=>useContext(WorkspaceNavigationContext)
