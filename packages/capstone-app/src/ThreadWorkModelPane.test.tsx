import {afterEach, expect, it, vi} from 'vitest'
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react'
import {useState, type ComponentProps} from 'react'
import ThreadWorkAdapter from './ThreadWorkAdapter'
import type ThreadWorkspace from './ThreadWorkspace'
import type {ThreadModelPaneProps} from './ThreadModelPane'
import type {CapstoneAssistantThreadProps} from './CapstoneAssistantThread'
import {HttpThreadTransport} from './threadHttpTransport'
import {parseWorkSnapshot, type WorkCommand} from './threadWorkProtocol'
import {ThreadProjectionStore, type ThreadProjectionState, type ThreadNetworkTask} from './threadProjectionStore'
import {sampleDiagramView} from './networkFixture'
import type GridSourceWorkspace from './GridSourceWorkspace'
import type {EventEnvelope} from './threadProtocol'
import {SessionReadingProvider} from './workspaceSessionCache'

vi.mock('./ThreadWorkspace',()=>({default:(props:ComponentProps<typeof ThreadWorkspace>)=><>
  {props.children}<button onClick={()=>props.onResourcePanelOpenChange?.(true)}>Show resources</button>
  <button onClick={()=>props.onResourcePanelOpenChange?.(false)}>Close resources</button>
  <output data-testid="resource-open">{String(props.resourcePanelOpen)}</output>
  <output data-testid="selected-resource">{props.selectedResourceView}</output>
  {props.resourcePanelOpen&&props.resourceViews?.map(view=><section key={view.id}>
    <button onClick={()=>props.onResourceViewChange?.(view.id)}>{view.label}</button>
    {props.selectedResourceView===view.id&&view.content}
  </section>)}
</>}))
vi.mock('./CapstoneAssistantThread',()=>({projectAssistantActivity:()=>undefined,projectAssistantMessages:()=>[],
  default:(props:CapstoneAssistantThreadProps)=><>{props.composerControls?.(null,{addMaterial:()=>{}})}{props.networkAttemptIds?.map(id=><button key={id} onClick={()=>props.onShowNetwork?.(id)}>View instruction {id}</button>)}</>}))
vi.mock('./ThreadModelDirectory',()=>({default:({onSwitch,onActivate}:{onSwitch:(id:string)=>void;onActivate:(id:string)=>void})=><>
  <button onClick={()=>onSwitch('ieee39')}>Open registered model</button>
  <button onClick={()=>onActivate('mdl_one')}>Activate registered model</button>
</>}))
vi.mock('./ThreadModelPane',()=>({default:(props:ThreadModelPaneProps)=><output data-testid="formal-pane">{JSON.stringify({
  context:props.snapshot.activeModelContext.id,view:props.networkView?.diagram.ref??null,
  preview:props.previewDiagram,historical:props.isHistorical,page:props.viewedPage,feedback:props.feedback,
  instructionLabel:props.instructionLabel,networkTaskId:props.networkTaskId??null,
})}</output>}))
vi.mock('./ThreadProductsWorkspace',()=>({default:()=>null}))
vi.mock('./ThreadMaterialUpload',()=>({default:()=>null}))
vi.mock('./GridSourceWorkspace',()=>({default:(props:ComponentProps<typeof GridSourceWorkspace>)=>{
  const [initialScope]=useState(props.requestedView?.scope_id??'north')
  return <><output data-testid="source-pane">{JSON.stringify({request:props.requestedView,nonce:props.requestNonce,initialScope})}</output><button onClick={props.onManualNavigate}>Manual source navigation</button></>
}}))

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
  let tasks:ThreadNetworkTask[]=[]
  let publicEvents:EventEnvelope[]=[]
  const publish=()=>listeners.forEach(fn=>fn())
  const restore=vi.fn(async(_id:string)=>'page_ieee39')
  const refresh=vi.fn(async()=>{})
  const dispatch=vi.fn(async(command:WorkCommand)=>{
    const next=work('ctx_one');state={...state,workSnapshot:next,snapshot:next.professionalSnapshot!};publish()
    return {status:'accepted',target:{kind:'model_workspace',id:'thr_formal'},commandId:command.command_id}
  })
  const store={get state(){return state},get publicEvents(){return publicEvents},canStreamEvents:false,
    get networkTasks(){return tasks},
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
  const view={...sampleDiagramView,diagram:{...sampleDiagramView.diagram,model:{id:'ieee39',revision:'revision:one',source:'gridctl'}},layer:{...sampleDiagramView.layer,model_revision:'revision:one'}}
  return {store,transport,restore,refresh,dispatch,view,
    setTasks(value:ThreadNetworkTask[]){tasks=value;publish()},
    setEvents(value:EventEnvelope[]){publicEvents=value;state={...state,eventSeq:Math.max(0,...value.map(event=>event.eventSeq))};publish()},
    setContext(id:string){const next=work(id);state={...state,snapshot:next.professionalSnapshot!,workSnapshot:next};publish()},
    setWorkContextOnly(id:string|null){state={...state,workSnapshot:work(id)};publish()},
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

it.each(['none','other-context','copied-view','exact-layer','baseline'])('labels only the exact admitted task view (%s)',async match=>{
  const server=fixture()
  server.admit('ctx_one')
  if(match!=='none')server.setTasks([{attemptId:'attempt_grid_saved',eventSeq:4,pageId:'page_ieee39',
    context:{...server.store.state.snapshot!.activeModelContext,id:match==='other-context'?'ctx_other':'ctx_one'},
    view:match==='copied-view'?structuredClone(server.view):server.view,presentationSource:match==='baseline'?'historical_baseline':'admitted_layer'}])
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="formal" preparedStore={server.store}/> )
  await waitFor(()=>expect(server.refresh).toHaveBeenCalledOnce())
  fireEvent.click(screen.getByText('Show resources'));fireEvent.click(await screen.findByText('电气拓扑'))
  const pane=JSON.parse(screen.getByTestId('formal-pane').textContent!)
  expect(pane.instructionLabel).toBe(match==='exact-layer'?'已保存任务图层':'模型基础拓扑')
  expect(pane.networkTaskId).toBe(match==='exact-layer'?'attempt_grid_saved':null)
})

const sourceRequest={schema:'capstone-grid-source-view-request/1' as const,source_id:'data-gateway' as const,scope_id:'north',scope_name:'华北',level:null,selected_object_id:null,view_ref:'verified-source',source_snapshot:{metadata_snapshot:'snapshot',source_instance:'gateway'},voltage_min_kv:330,display_grouping_only:false}
const instruction=(eventSeq:number,attemptId:string):EventEnvelope=>({eventId:`accepted${eventSeq}`,eventSeq,eventType:'command_accepted',eventVersion:1,threadId:'thr_formal',runId:'run_formal',attemptId,visibility:'public',occurredAt:'2026-10-26T00:00:00Z',payload:{kind:'send_message',payload:{text:'Actual instruction'}}})
const sourceEvent=(eventSeq:number,attemptId:string,viewRef=sourceRequest.view_ref):EventEnvelope=>({...instruction(eventSeq,attemptId),eventId:`source${eventSeq}`,eventType:'runtime_event',payload:{source_view:{...sourceRequest,view_ref:viewRef}}})
it('restores each instruction source view from the existing answer toolbar without rerunning tools',async()=>{
  const server=fixture(null)
  const events=[instruction(1,'overview'),sourceEvent(2,'overview','root-view')]
  server.setEvents(events)
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing-history" preparedStore={server.store}/>)
  await screen.findByTestId('source-pane')
  await act(async()=>server.setEvents([...events,instruction(3,'station'),sourceEvent(4,'station','station-view')]))
  expect(JSON.parse(screen.getByTestId('source-pane').textContent!).request.view_ref).toBe('station-view')
  fireEvent.click(screen.getByText('View instruction overview'))
  expect(JSON.parse(screen.getByTestId('source-pane').textContent!).request.view_ref).toBe('root-view')
  // New events in the current instruction must not steal a manually restored view.
  await act(async()=>server.setEvents([...events,instruction(3,'station'),sourceEvent(5,'station','station-view')]))
  expect(JSON.parse(screen.getByTestId('source-pane').textContent!).request.view_ref).toBe('root-view')
  fireEvent.click(screen.getByText('View instruction station'))
  expect(JSON.parse(screen.getByTestId('source-pane').textContent!).request.view_ref).toBe('station-view')
  expect(server.dispatch).not.toHaveBeenCalled()
})
it('keeps the opened source view mounted while a later plain instruction runs',async()=>{
  const server=fixture(null)
  server.setEvents([instruction(1,'attempt_source'),sourceEvent(2,'attempt_source')])
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing" preparedStore={server.store}/> )
  const source=JSON.parse((await screen.findByTestId('source-pane')).textContent!)
  expect(source.request).toEqual(sourceRequest);expect(source.nonce).toBe(1)
  await act(async()=>server.setEvents([instruction(1,'attempt_source'),sourceEvent(2,'attempt_source'),instruction(3,'attempt_plain')]))
  expect(screen.getByTestId('resource-open').textContent).toBe('true')
  expect(screen.getByTestId('selected-resource').textContent).toBe('source-topology')
  expect(JSON.parse(screen.getByTestId('source-pane').textContent!)).toEqual(source)
})
it('retains manual source navigation and panel closure over later proposals in the same instruction',async()=>{
  const server=fixture(null)
  server.setEvents([instruction(1,'attempt_source'),sourceEvent(2,'attempt_source')])
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing-manual" preparedStore={server.store}/> )
  await screen.findByTestId('source-pane')
  fireEvent.click(screen.getByText('Manual source navigation'))
  await act(async()=>server.setEvents([instruction(1,'attempt_source'),sourceEvent(2,'attempt_source'),sourceEvent(4,'attempt_source','newer-source')]))
  expect(JSON.parse(screen.getByTestId('source-pane').textContent!).request.view_ref).toBe('verified-source')
  fireEvent.click(screen.getByText('Close resources'))
  await act(async()=>server.setEvents([instruction(1,'attempt_source'),sourceEvent(5,'attempt_source','latest-source')]))
  expect(screen.getByTestId('resource-open').textContent).toBe('false')
})
it('deduplicates repeated identical source pages and keeps the request nonce across session remounts',async()=>{
  const server=fixture(null)
  server.setEvents([instruction(1,'attempt_source'),sourceEvent(2,'attempt_source')])
  const tree=()=> <SessionReadingProvider namespace="routing-cache" threadId="thr_formal"><ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing-cache" preparedStore={server.store}/></SessionReadingProvider>
  const first=render(tree())
  await screen.findByTestId('source-pane')
  await act(async()=>server.setEvents([instruction(1,'attempt_source'),sourceEvent(2,'attempt_source'),sourceEvent(3,'attempt_source')]))
  expect(JSON.parse(screen.getByTestId('source-pane').textContent!).nonce).toBe(1)
  first.unmount();render(tree())
  expect(JSON.parse((await screen.findByTestId('source-pane')).textContent!).nonce).toBe(1)
})
it('does not replace a saved child with an older history page during refresh',async()=>{
  const server=fixture(null),root=[instruction(1,'root'),sourceEvent(2,'root','root-view')]
  server.setEvents([...root,instruction(3,'child'),sourceEvent(4,'child','child-view')])
  const tree=()=> <SessionReadingProvider namespace="routing-refresh" threadId="thr_formal"><ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing-refresh" preparedStore={server.store}/></SessionReadingProvider>
  const first=render(tree());await screen.findByTestId('source-pane')
  fireEvent.click(screen.getByText('View instruction child'))
  first.unmount();server.setEvents(root);render(tree())
  expect(JSON.parse((await screen.findByTestId('source-pane')).textContent!).request.view_ref).toBe('child-view')
})
it('switches source to the later admitted current model task and ignores a historical baseline',async()=>{
  const server=fixture();server.admit('ctx_one')
  server.setEvents([instruction(1,'attempt_current'),sourceEvent(2,'attempt_current')])
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing-mixed" preparedStore={server.store}/> )
  await screen.findByTestId('source-pane')
  await act(async()=>server.setTasks([{attemptId:'attempt_current',eventSeq:3,pageId:'page_ieee39',context:server.store.state.snapshot!.activeModelContext,view:server.view,presentationSource:'historical_baseline'}]))
  expect(screen.getByTestId('selected-resource').textContent).toBe('source-topology')
  await act(async()=>server.setTasks([{attemptId:'attempt_current',eventSeq:4,pageId:'page_ieee39',context:server.store.state.snapshot!.activeModelContext,view:server.view,presentationSource:'admitted_layer'}]))
  await waitFor(()=>expect(screen.getByTestId('selected-resource').textContent).toBe('model'))
  expect(JSON.parse(screen.getByTestId('formal-pane').textContent!).networkTaskId).toBe('attempt_current')
})

it('remounts scope-owned source state when a later verified instruction selects another scope',async()=>{
  const server=fixture()
  server.setEvents([instruction(1,'attempt_current'),sourceEvent(2,'attempt_current')])
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing-scope" preparedStore={server.store}/> )
  const first=JSON.parse((await screen.findByTestId('source-pane')).textContent!)
  const next=sourceEvent(3,'attempt_current')
  next.payload={...next.payload,source_view:{...sourceRequest,scope_id:'east',scope_name:'East'}}
  await act(async()=>server.setEvents([instruction(1,'attempt_current'),next]))
  await waitFor(()=>expect(JSON.parse(screen.getByTestId('source-pane').textContent!).initialScope).toBe('east'))
  expect(first.initialScope).not.toBe('east')
})

it('does not retain a stale professional context after the Work model is cleared',async()=>{
  const server=fixture();server.admit('ctx_one')
  render(<ThreadWorkAdapter transport={server.transport} threadId="thr_formal" namespace="routing-close" preparedStore={server.store}/> )
  fireEvent.click(screen.getByText('Show resources'));fireEvent.click(await screen.findByText('电气拓扑'))
  expect(screen.getByTestId('formal-pane')).toBeTruthy()
  await act(async()=>server.setWorkContextOnly(null))
  expect(screen.queryByTestId('formal-pane')).toBeNull()
  expect(screen.queryByText('电气拓扑')).toBeNull()
  expect(server.store.state.snapshot?.activeModelContext.id).toBe('ctx_one')
})
