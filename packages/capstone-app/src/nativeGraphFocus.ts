import type {EventEnvelope} from './threadProtocol'
import type {ExecutionGraph,GraphSourceVersion} from './executionGraph'

const object=(value:unknown):Record<string,unknown>|undefined=>value!==null&&typeof value==='object'&&!Array.isArray(value)?value as Record<string,unknown>:undefined
const nonempty=(value:unknown)=>Array.isArray(value)&&value.length>0
const materialRef=(value:unknown)=>typeof value==='string'&&/^(?:material|resource)_[a-f0-9]{32}$/.test(value)
const frozenResourceScope=(refs:readonly string[]|undefined,versions:readonly GraphSourceVersion[]|undefined)=>
  refs?.some(ref=>{
    const match=/^resource:resource_[a-f0-9]{32}:[1-9][0-9]*:([a-f0-9]{64})$/.exec(ref)
    return match&&versions?.some(version=>version.ref===ref&&version.revision===`sha256:${match[1]}`)
  })??false

/** Presentation only. A native organization graph does not itself classify business work. */
export function nativeGraphFocus(events:readonly EventEnvelope[],attemptId:string,graph:ExecutionGraph|undefined):'tools'|'tasks'|undefined {
  if(!graph)return
  const current=events.filter(event=>event.attemptId===attemptId&&event.visibility==='public')
  const plan=current.find(event=>event.eventType==='turn_plan_created'&&event.payload.source==='native_conversation'&&event.payload.plan_revision==='turn-native-conversation-v1')
  if(!plan)return // Preserve historical graphs that do not record the native selection contract.
  // The admitted graph cross-checks owner, action leases and node/action source scopes.
  // Uploaded sources can enter through selected history even when Work grants are empty.
  const snapshots=[graph.current,...graph.checkpoints.map(item=>item.graph),...graph.revisions.map(item=>item.graph)]
  if(snapshots.some(snapshot=>snapshot.nodes.some(node=>frozenResourceScope(node.source_refs,node.selected_source_versions))||
    snapshot.actions.some(action=>frozenResourceScope(action.source_refs,action.source_versions)))||
    graph.executions.some(execution=>frozenResourceScope(execution.node.source_refs,execution.node.selected_source_versions)||
      frozenResourceScope(execution.action.source_refs,execution.action.source_versions)))return 'tasks'
  const accepted=object(plan.payload.accepted_context)
  if(nonempty(accepted?.objects)||nonempty(accepted?.materials))return 'tasks'
  for(const event of current) {
    if(event.eventType==='command_accepted') {
      const work=object(event.payload.work),context=object(work?.task_context),binding=object(context?.binding),input=object(event.payload.payload)
      // Only the host-accepted current Work binding and selected durable materials count.
      if(binding?.thread_id===event.threadId&&binding?.work_id===work?.work_id&&
        (nonempty(context?.model_contexts)||(Array.isArray(context?.resource_refs)&&context.resource_refs.some(materialRef))))return 'tasks'
      if([input?.material_refs,event.payload.attachment_refs].some(refs=>Array.isArray(refs)&&refs.some(materialRef)))return 'tasks'
    }
    const admission=object(event.payload.admission)
    if(event.eventType==='attempt_completed'&&admission?.mode==='authority_backed'&&admission.assurance==='lineage_verified'&&
      nonempty(event.payload.result_refs)&&nonempty(event.payload.evidence_refs))return 'tasks'
  }
  // Graph projection admits exact owners, checkpoints, tool bindings and actual activity.
  // A raw tool_name on an unrelated runtime event cannot select business presentation.
  return graph.executions.some(execution=>execution.tools.some(tool=>tool.name.startsWith('data_gateway_')))?'tasks':'tools'
}
