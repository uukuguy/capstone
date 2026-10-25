import {afterEach, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import type {ComponentProps} from 'react'
import ThreadWorkAdapter from './ThreadWorkAdapter'
import type ThreadWorkspace from './ThreadWorkspace'
import type {ThreadModelPaneProps} from './ThreadModelPane'
import type {CapstoneAssistantThreadProps} from './CapstoneAssistantThread'
import {HttpThreadTransport} from './threadHttpTransport'
import {parseWorkSnapshot, type WorkCommand} from './threadWorkProtocol'
import {ThreadProjectionStore, type ThreadProjectionState} from './threadProjectionStore'
import {sampleDiagramView} from './networkFixture'

vi.mock('./ThreadWorkspace',()=>({default:(props:ComponentProps<typeof ThreadWorkspace>)=><>
  {props.children}<button onClick={()=>props.onResourcePanelOpenChange?.(true)}>Show resources</button>
  <output data-testid="selected-resource">{props.selectedResourceView}</output>
  {props.resourcePanelOpen&&props.resourceViews?.map(view=><section key={view.id}>
    <button onClick={()=>props.onResourceViewChange?.(view.id)}>{view.label}</button>
    {props.selectedResourceView===view.id&&view.content}
  </section>)}
</>}))
vi.mock('./CapstoneAssistantThread',()=>({projectAssistantActivity:()=>undefined,projectAssistantMessages:()=>[],
  default:(props:CapstoneAssistantThreadProps)=><>{props.composerControls?.(null,{addMaterial:()=>{}})}</>}))
vi.mock('./ThreadModelDirectory',()=>({default:({onSwitch,onActivate}:{onSwitch:(id:string)=>void;onActivate:(id:string)=>void})=><>
  <button onClick={()=>onSwitch('ieee39')}>Open registered model</button>
  <button onClick={()=>onActivate('mdl_one')}>Activate registered model</button>
</>}))
vi.mock('./ThreadModelPane',()=>({default:(props:ThreadModelPaneProps)=><output data-testid="formal-pane">{JSON.stringify({
  context:props.snapshot.activeModelContext.id,view:props.networkView?.diagram.ref??null,
  preview:props.previewDiagram,historical:props.isHistorical,page:props.viewedPage,feedback:props.feedback,
})}</output>}))
vi.mock('./ThreadProductsWorkspace',()=>({default:()=>null}))
vi.mock('./ThreadMaterialUpload',()=>({default:()=>null}))

afterEach(()=>{cleanup();vi.unstubAllGlobals();localStorage.clear();sessionStorage.clear()})

function fixture(initialContext:string|null='ctx_one'){
  const model={id:'ctx_one',model_id:'ieee39',model_revision:'revision:one',implementation_family:'pandapower',selection_revision:'sel_one'}
  const workspace=(context:string|null)=>({threadId:'thr_formal',runId:'run_formal',eventSeq:0,currentEntryId:context?'mdl_one':null,
    models:context?[{entryId:'mdl_one',modelId:'ieee39',modelRevision:'revision:one',implementationFamily:'pandapower',authorityModelRef:'gridctl:ieee39',displayName:'IEEE-39',diagramProviderId:'gridctl',lastActiveSeq:0}]:[],blockedReason:null})
  function work(context:string|null){return parseWorkSnapshot({schema:'capstone-thread-snapshot/2',minimum_protocol_version:2,
    thread_id:'thr_formal',run:{run_id:'run_formal',state:'open'},active_model_context:context?{...model,id:context}:null,
    active_grid_page_id:context?'page_ieee39':null,selected_model_context_id:context,current_attempt:null,
    last_event_seq:0,base_event_seq:0,works:[],task_context:null,session_type:'enterprise-research',
    native_execution:{available:!context,unavailable_reason:context?'model_selected':null}})}
  const initial=work(initialContext)
  let state:ThreadProjectionState={connection:'live',snapshot:initial.professionalSnapshot??null,workSnapshot:initial,
    eventSeq:0,resyncRequired:false,pendingCommands:[],viewedGridPageId:initialContext?'page_ieee39':null,
    catalog:{models:[],profiles:[]},networkView:null,gridPages:[],hasOlderHistory:false,historyLoading:false,historyAtLatest:true}
  const listeners=new Set<()=>void>()
  const publish=()=>listeners.forEach(fn=>fn())
  const restore=vi.fn(async(_id:string)=>'page_ieee39')
  const refresh=vi.fn(async()=>{})
  const dispatch=vi.fn(async(command:WorkCommand)=>{
    const next=work('ctx_one');state={...state,workSnapshot:next,snapshot:next.professionalSnapshot!};publish()
    return {status:'accepted',target:{kind:'model_workspace',id:'thr_formal'},commandId:command.command_id}
  })
  const store={get state(){return state},publicEvents:[],canStreamEvents:false,
    get modelWorkingPages(){return []},subscribe:(fn:()=>void)=>{listeners.add(fn);return()=>listeners.delete(fn)},
    catchUp:async()=>{},load:async()=>{},dispose:()=>{},refreshWorkSnapshot:async()=>{},dispatch,
    restoreHistoricalNetwork:restore,refreshModels:refresh,
    viewGridPage:(id:string)=>{state={...state,viewedGridPageId:id};publish()},
  } as unknown as ThreadProjectionStore
  const fetcher=vi.fn(async(url:RequestInfo|URL)=>{
    if(String(url).includes('/models')){
      const value=workspace(state.workSnapshot?.modelContext?.id??null)
      return Response.json({schema:'capstone-thread-model-workspace/1',thread_id:value.threadId,run_id:value.runId,event_seq:0,
        current_entry_id:value.currentEntryId,models:value.models.map(m=>({entry_id:m.entryId,model_id:m.modelId,model_revision:m.modelRevision,
          implementation_family:m.implementationFamily,authority_model_ref:m.authorityModelRef,display_name:m.displayName,
          diagram_provider_id:m.diagramProviderId,last_active_seq:0})),blocked_reason:null},{headers:{'Capstone-Thread-Version':'2'}})
    }
    return new Response('{}',{status:404})
  })
  const transport=new HttpThreadTransport('','',fetcher,'/api/v1/threads','2')
  const view={...sampleDiagramView,diagram:{...sampleDiagramView.diagram,model:{id:'ieee39',revision:'revision:one',source:'gridctl'}}}
  return {store,transport,restore,refresh,dispatch,view,
    setContext(id:string){const next=work(id);state={...state,snapshot:next.professionalSnapshot!,workSnapshot:next};publish()},
    admit(id:string,pageId='page_ieee39'){const context=state.snapshot!.activeModelContext;state={...state,networkView:view,
      gridPages:[...state.gridPages.filter(page=>page.context.id!==id),{pageId,context:{...context,id},networkView:view}]};publish()},
  }
}

it('restores the exact context once and exposes the admitted formal view separately from source topology',async()=>{
  const server=fixture()
  server.restore.mockImplementation(async(id)=>{server.admit(id);return 'page_ieee39'})
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  await waitFor(()=>expect(server.refresh).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByText('Show resources'))
  fireEvent.click(await screen.findByText('电气拓扑'))
  expect(JSON.parse(screen.getByTestId('formal-pane').textContent!).context).toBe('ctx_one')
  expect(JSON.parse(screen.getByTestId('formal-pane').textContent!).view).toBe(server.view.diagram.ref)
  expect(server.restore).toHaveBeenCalledExactlyOnceWith('ctx_one')
  expect(screen.getByText('源电网')).toBeTruthy()
})

it('never reuses a non-null diagram from the same model revision under a reopened context',async()=>{
  const server=fixture()
  server.admit('ctx_one')
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  await waitFor(()=>expect(server.refresh).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByText('Show resources'));fireEvent.click(await screen.findByText('电气拓扑'))
  await act(async()=>{server.setContext('ctx_reopened')})
  await waitFor(()=>expect(server.restore).toHaveBeenCalledWith('ctx_reopened'))
  const pane=JSON.parse(screen.getByTestId('formal-pane').textContent!)
  expect(pane.context).toBe('ctx_reopened');expect(pane.view).toBeNull();expect(pane.preview).toBeNull()
  expect(pane.historical).toBe(false)
})

it.each(['Open registered model','Activate registered model'])('opens the formal resource after accepted %s',async action=>{
  const server=fixture(null)
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  fireEvent.click(await screen.findByText(action))
  await waitFor(()=>expect(screen.getByTestId('selected-resource').textContent).toBe('model'))
  expect(server.dispatch).toHaveBeenCalledOnce()
  expect(screen.getByTestId('formal-pane')).toBeTruthy()
})

it('keeps rejected model commands from opening a different resource view',async()=>{
  const server=fixture(null)
  server.dispatch.mockResolvedValueOnce({status:'rejected',target:{kind:'model_workspace',id:'thr_formal'},commandId:'rejected'})
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  fireEvent.click(await screen.findByText('Open registered model'))
  await waitFor(()=>expect(server.dispatch).toHaveBeenCalledOnce())
  expect(screen.getByTestId('selected-resource').textContent).toBe('products')
  expect(screen.queryByTestId('formal-pane')).toBeNull()
})

it('ignores a superseded restoration error and refreshes the reopened context',async()=>{
  const server=fixture()
  let rejectOld!:(reason:Error)=>void
  server.restore.mockImplementationOnce(()=>new Promise<string>((_,reject)=>{rejectOld=reject}))
  server.restore.mockImplementation(async id=>{server.admit(id);return 'page_ieee39'})
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  await waitFor(()=>expect(server.restore).toHaveBeenCalledWith('ctx_one'))
  await act(async()=>{server.setContext('ctx_reopened');rejectOld(new Error('old context failed'))})
  await waitFor(()=>expect(server.refresh).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByText('Show resources'));fireEvent.click(await screen.findByText('电气拓扑'))
  const pane=JSON.parse(screen.getByTestId('formal-pane').textContent!)
  expect(pane.context).toBe('ctx_reopened');expect(pane.feedback).toBeNull()
  expect(server.restore).toHaveBeenCalledTimes(2)
})

it('navigates an admitted historical page without activating its model context',async()=>{
  const server=fixture('ctx_current')
  server.admit('ctx_current');server.admit('ctx_past','history')
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  await waitFor(()=>expect(server.refresh).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByText('Show resources'));fireEvent.click(await screen.findByText('电气拓扑'))
  fireEvent.change(screen.getByRole('combobox',{name:'电气拓扑视图'}),{target:{value:'history'}})
  const pane=JSON.parse(screen.getByTestId('formal-pane').textContent!)
  expect(pane.historical).toBe(true);expect(pane.page).toBe('history')
  expect(server.store.state.snapshot?.activeModelContext.id).toBe('ctx_current')
  expect(server.dispatch).not.toHaveBeenCalled()
})

it('reports a current restoration failure without inventing a preview diagram',async()=>{
  const server=fixture()
  server.restore.mockRejectedValueOnce(new Error('network observation unavailable'))
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  await waitFor(()=>expect(server.restore).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByText('Show resources'));fireEvent.click(await screen.findByText('电气拓扑'))
  await waitFor(()=>expect(JSON.parse(screen.getByTestId('formal-pane').textContent!).feedback).toContain('电气拓扑暂时无法恢复'))
  const pane=JSON.parse(screen.getByTestId('formal-pane').textContent!)
  expect(pane.view).toBeNull();expect(pane.preview).toBeNull()
  expect(server.store.state.snapshot?.activeModelContext.id).toBe('ctx_one')
})
