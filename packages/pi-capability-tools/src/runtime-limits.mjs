// Neutral library defaults. The application passes its resolved initialization
// snapshot; this module never reads application files or environment policy.
export const DEFAULT_RUNTIME_LIMITS = Object.freeze({
  control_document_bytes:33554432,rpc_frame_bytes:8388608,rpc_batch_requests:128,
  tool_timeout_seconds:1800,tool_observation_bytes:4194304,
  research_request_bytes:67108864,research_response_bytes:268435456,
  research_claim_count:512,research_note_count:1024,research_question_count:256,
  research_text_chars:33554432,research_summary_chars:65536,context_references:4096,
  research_goal_chars:65536,research_progress_chars:16384,research_page_records:512,
  guide_resource_count:512,guide_document_bytes:4194304,guide_total_bytes:33554432,
  guide_title_chars:4096,decision_text_chars:65536,decision_references:4096,diagnostic_tail_bytes:1048576,
  context_segment_bytes:67108864,context_manifest_bytes:1048576,answer_summary_chars:4096,
  diagnostic_error_count:128,diagnostic_path_parts:64,diagnostic_path_chars:4096,
  diagnostic_text_chars:16384,context_marker_bytes:1048576,
  research_round_count:64,research_finding_count:4096,research_snapshot_bytes:16777216,
});
const modes=new WeakMap();
const debugListeners=new Set();
export function onDebugCapacityExceeded(listener){
  if(typeof listener!=='function')throw new TypeError('debug capacity listener must be a function');
  debugListeners.add(listener);return ()=>debugListeners.delete(listener);
}

export function runtimeLimits(overrides, options={}) {
  if (overrides !== undefined && (overrides === null || typeof overrides !== 'object' || Array.isArray(overrides))) {
    throw new TypeError('runtime_limits must be an object');
  }
  const mode=options.mode??runtimeLimitMode(overrides);
  if(!['normal','debug'].includes(mode))throw new TypeError('runtime limit mode must be normal or debug');
  const result = {...DEFAULT_RUNTIME_LIMITS};
  for (const [key,value] of Object.entries(overrides ?? {})) {
    if (!Number.isSafeInteger(value) || value < (key === 'provider_stream_bytes' ? 0 : 1)) {
      throw new TypeError(`invalid runtime capacity: ${key}`);
    }
    result[key]=value;
  }
  modes.set(result,mode);
  return Object.freeze(result);
}

export function runtimeLimitMode(limits){return limits&&typeof limits==='object'?modes.get(limits)??'normal':'normal';}

export class CapacityExceeded extends Error {
  constructor(limits,dimension,actual,unit,phase,{mode=runtimeLimitMode(limits)}={}){
    super(`capacity_exceeded: ${dimension} actual=${actual} limit=${limits[dimension]} ${unit} phase=${phase}`);
    this.name='CapacityExceeded';
    const detail={code:'capacity_exceeded',dimension,actual,limit:limits[dimension],unit,phase,retryable:false,
      ...(mode==='debug'?{mode:'debug'}:{})};
    Object.assign(this,detail,{capacity:detail});
    if(mode==='debug')for(const listener of debugListeners){try{listener(this);}catch{/* The typed interruption must remain the original cause. */}}
  }
}

export function checkCapacity(limits, dimension, actual, unit, phase) {
  requireDimension(limits,dimension);
  if (actual > limits[dimension]) {
    throw new CapacityExceeded(limits,dimension,actual,unit,phase);
  }
}

export function observeCapacity(limits,dimension,actual,unit,phase){
  requireDimension(limits,dimension);
  const exceeded=actual>limits[dimension];
  if(exceeded&&runtimeLimitMode(limits)==='debug')checkCapacity(limits,dimension,actual,unit,phase);
  return exceeded;
}

function requireDimension(limits,dimension){
  if(typeof limits?.[dimension]!=='number'||!Number.isFinite(limits[dimension])||limits[dimension]<0)
    throw new TypeError(`unknown or invalid runtime capacity: ${dimension}`);
}

export function sameRuntimeLimits(left,right) {
  const a=runtimeLimits(left),b=runtimeLimits(right);
  return Object.keys(a).length===Object.keys(b).length && Object.keys(a).every(key=>a[key]===b[key]);
}
