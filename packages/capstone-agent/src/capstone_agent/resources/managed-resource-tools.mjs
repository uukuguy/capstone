/** Installed capabilities stay behind one typed, host-authorized resource adapter. */
export function createManagedResourceTools(config,{fetchImpl=globalThis.fetch}={}){
 if(!config.managedResources||!Array.isArray(config.managedResources.allowed_actions))return [];
 const granted=new Set(config.managedResources.allowed_actions);
 const operations=[];
 if(granted.has('resources.use'))operations.push('list','operation','discover','call','load_skill');
 if(granted.has('resources.install')||granted.has('resources.update'))operations.push('install');
 if(granted.has('resources.enable')||granted.has('resources.disable'))operations.push('state');
 if(granted.has('resources.uninstall'))operations.push('uninstall');
 if(granted.has('resources.preinstall.manage'))operations.push('preinstall_draft','preinstall_export','preinstall_publish','preinstall_import');
 if(!operations.length)return [];
 return [{name:'agent_managed_resource',label:'管理与使用安装资源',
 description:'Current permission snapshot: '+[...granted].join(', ')+'. List, install, update, enable/disable, uninstall and use persistent Skills/MCP for this workspace. First list to read allowed_actions and exact versions. Install requires request_id, resource_id and request {kind:skill|mcp_local|mcp_remote,source:{locator,revision},subdirectory?,runtime?}; use an exact Git commit for packages, or revision discover for a remote MCP to pin its actual publication. Installation success is not task use. For MCP discover with exact resource_id/version, then call with returned exact name, arguments and catalog_revision. For Skills load_skill returns admitted read-only package paths; read the SKILL.md and follow its relative resources. Do not invent tool contracts or repeat uncertain calls. Installing does not grant business data authority or change the data-gateway binding. Operations are permission and network checked by the host. Preinstall draft/publish changes defaults, not other deployed servers.',
 parameters:{type:'object',properties:{operation:{type:'string',enum:operations},document:{type:'object'}},required:['operation','document'],additionalProperties:false},
 async execute(callId,args,signal){
  const remaining=config.deadlineAt-Date.now();if(remaining<=0)throw Error('resource_task_deadline');
  let response,value;
  try{
   response=await fetchImpl(config.managedResources.url,{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+config.managedResources.grant},body:JSON.stringify(args),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(remaining)]):AbortSignal.timeout(remaining)});
   value=await response.json();
  }catch(error){
   signal?.throwIfAborted();
   return {isError:true,content:[{type:'text',text:JSON.stringify({code:'resource_operation_outcome_unknown',executed:null,request_id:args.document?.request_id,recovery:'Do not repeat an uncertain mutation. Query its original operation receipt first.'})}],details:{resource_operation:args.operation,tool_call_id:callId}};
  }
  return {isError:!response.ok||value.ok!==true||value.result?.status==='failed'||args.operation==='call'&&value.result?.result?.isError===true,content:[{type:'text',text:JSON.stringify(value.ok===true?value.result:value)}],details:{resource_operation:args.operation,tool_call_id:callId}};
 }}];
}
