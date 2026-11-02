import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,readFileSync,writeFileSync,readdirSync,renameSync,rmSync,cpSync,symlinkSync,realpathSync,chmodSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve,dirname} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {spawn,execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const root=fileURLToPath(new URL('../../../../',import.meta.url));

for(const scenario of ['automatic-work','automatic-ready-work','full-cycle','init-rejection','unplanned-work','delegated-work','limited-delivery','limited-checker','producer-checkpoint','mcp-work','direct-chat','discovery-branches','adoption-branches','ready-batch','split-only','state-recovery','long-state-recovery','review-version-recovery','shell-pipelines'])test('actual pinned SDK: '+scenario, {timeout:20000},async()=>{
  const automaticScenario=scenario.startsWith('automatic-');
  const recoveryScenario=['state-recovery','long-state-recovery'].includes(scenario);
  const versionRecovery=scenario==='review-version-recovery';
  const discoveryDriven=['discovery-branches','adoption-branches','ready-batch'].includes(scenario);
  const dir=realpathSync(mkdtempSync(join(tmpdir(),'enterprise-actual-sdk-')));
  const channel=join(dir,'channel'),workspace=join(dir,'workspace'),agent=join(dir,'agent');
  for(const path of [channel,join(channel,'requests'),join(channel,'receipts'),workspace,agent])mkdirSync(path,{recursive:true});
  const sdk=join(root,'.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js');
  assert.ok(readFileSync(sdk).length,'Install managed Pi before this acceptance test');
  // Production stages the SDK resolution links next to the copied adapter.
  // Reproduce that installation layout without changing repository runtimes.
  const resources=join(dir,'resources');
  cpSync(join(root,'packages/capstone-agent/src/capstone_agent/resources'),resources,{recursive:true});
  const scope=join(resources,'node_modules/@earendil-works');mkdirSync(scope,{recursive:true});
  symlinkSync(resolve(dirname(sdk),'..'),join(scope,'pi-coding-agent'),'dir');
  symlinkSync(resolve(dirname(sdk),'../../ai'),join(scope,'pi-ai'),'dir');
  const schemas=JSON.parse(execFileSync(join(root,'packages/capstone-agent/.venv/bin/python'),['-c',
    'import json;from capability_agent.application.research_models import research_tool_schemas,task_progress_tool_schema,research_depth_tool_schema;r,u=research_tool_schemas({"research_text_chars":'+(automaticScenario?33554432:scenario==='long-state-recovery'?262144:65536)+'});print(json.dumps({"read_tool_schema":r,"update_tool_schema":u,"progress_tool_schema":task_progress_tool_schema(),"depth_tool_schema":research_depth_tool_schema()}))'],{cwd:root,encoding:'utf8'}));
  const identity={run_id:'run-sdk',turn_id:'turn-sdk',attempt_id:'attempt-sdk',research_id:'research-sdk'};
  writeFileSync(join(channel,'binding.json'),JSON.stringify({schema_version:'capability-research-channel/1.0',...identity,...schemas}));
  let state=null,revision=0;const seen=new Set(),admitted=new Set(['material:source']),committedRevisions=new Map();
  const atomic=(path,value)=>{writeFileSync(path+'.tmp',JSON.stringify(value));renameSync(path+'.tmp',path);};
  const publish=()=>atomic(join(channel,'view.json'),{schema_version:'capability-research-view/1.0',...identity,research_revision:revision,state});
  publish();writeFileSync(join(workspace,'source.csv'),'value\n3\n7\n');
  const config={sdk,fixtureScenario:scenario,model:'offline-research-cycle',settings:{compaction:{enabled:false}},extensions:[],allowedSkills:[],
    researchOwner:{thread_id:'thread-sdk',work_id:'work-sdk',research_id:'research-sdk',goal_revision:1},researchAttemptId:'attempt-sdk',researchSources:['material:source'],contextFiles:[],input:{kind:'text',text:'Read source.csv, calculate the total and save the correct report.md.'},
    adapter_sha256:'offline',researchTaskId:'task-sdk',researchChannelPath:channel,deadlineAt:Date.now()+15000,
    runtimeLimits:{research_text_chars:scenario==='long-state-recovery'?262144:65536},researchRuntime:{enabled:true,deliveryReview:{enabled:versionRecovery||scenario==='limited-delivery'},limits:{maxRounds:3},delegation:{concurrency:discoveryDriven?2:1,maxTasks:4,maxTurns:10,graceTurns:2}},
    applicationPolicy:{allowed_tools:['read','write',...((['automatic-work','automatic-ready-work','delegated-work','limited-delivery'].includes(scenario)||recoveryScenario||versionRecovery||discoveryDriven)?['agent_delegate']:[]),'agent_research_cycle','agent_research_read','agent_research_update','agent_task_progress']}};
  const configPath=join(dir,'config.json');writeFileSync(configPath,JSON.stringify(config));
  if(automaticScenario){
    config.runtimeLimitMode='debug';
    config.researchRuntime.explicitSubtaskPlanning=true;
    config.researchRuntime.batchReadyInvestigations=scenario==='automatic-ready-work';
    if(scenario==='automatic-ready-work')config.researchRuntime.delegation.concurrency=2;
    // Match production checkpoint capacity while keeping the automatic summary
    // limit at 64 KiB: large retained results are not automatic context notes.
    config.runtimeLimits.research_text_chars=33554432;
    writeFileSync(configPath,JSON.stringify(config));
  }
  if(scenario==='limited-checker'){
    config.researchRuntime.gracefulExecutionClosure=true;
    config.applicationPolicy.allowed_tools.push('bash');
    config.input.text='Finish the existing draft for human review; retain known errors. Do not restart its analysis.';
    writeFileSync(join(workspace,'report.md'),'Total: 10\n');writeFileSync(join(workspace,'metrics.csv'),'total\n10\n');
    writeFileSync(configPath,JSON.stringify(config));
  }
  if(scenario==='producer-checkpoint'){
    config.researchRuntime.gracefulExecutionClosure=true;config.applicationPolicy.allowed_tools.push('bash');
    writeFileSync(configPath,JSON.stringify(config));
  }
  if(scenario==='delegated-work'){
    const prior=join(dir,'authorized-inputs');mkdirSync(prior);
    config.fixtureSourcePath=join(prior,'source.csv');writeFileSync(config.fixtureSourcePath,'value\n3\n7\n');chmodSync(config.fixtureSourcePath,0o440);
    config.contextFiles=[{path:'authorized-source',content:'Read-only prior source: '+config.fixtureSourcePath+'\nSOURCE_MANIFEST_SENTINEL'}];
    config.appendSystemPrompt=['PARENT_WORKFLOW_SENTINEL: own the full research plan, record and assessment.'];
    writeFileSync(configPath,JSON.stringify(config));
  }
  if(scenario==='shell-pipelines'){
    config.applicationPolicy.allowed_tools.push('bash');writeFileSync(configPath,JSON.stringify(config));
  }
  if(scenario==='split-only'||recoveryScenario||versionRecovery){
    config.applicationPolicy.allowed_tools=config.applicationPolicy.allowed_tools.filter(name=>name!=='agent_research_cycle');
    config.applicationPolicy.allowed_tools.push('agent_research_plan','agent_research_record','agent_research_assess');
    writeFileSync(configPath,JSON.stringify(config));
  }
  if(scenario==='mcp-work'){
    const interpreter=join(dir,'offline-mcp');
    writeFileSync(interpreter,'#!'+join(root,'packages/capstone-agent/.venv/bin/python')+'\n'+
      'import sys,json,pathlib\nc=json.loads(pathlib.Path(sys.argv[-1]).read_text())\n'+
      'print(json.dumps({"type":"mcp_ready","tool_schema_hashes":c["mcp"]["descriptor"]["tool_schema_hashes"]}),flush=True)\n'+
      'for line in sys.stdin:\n r=json.loads(line);values=pathlib.Path(c["mcp"]["workspace"],"source.csv").read_text().splitlines()[1:];print(json.dumps({"result_json":json.dumps({"total":sum(map(int,values))}),"observation":{},"is_error":False}),flush=True)\n');
    chmodSync(interpreter,0o700);config.interpreter=interpreter;config.configPath=configPath;
    config.mcp={workspace,descriptor:{tool_schemas:{source_total:{description:'Read the authorized source total',inputSchema:{type:'object',properties:{},additionalProperties:false}}},tool_schema_hashes:{source_total:'offline-schema'}}};
    config.extensions=[join(resources,'general-mcp.mjs')];config.applicationPolicy.allowed_tools.push('source_total');
    writeFileSync(configPath,JSON.stringify(config));
  }
  const child=spawn(process.execPath,[fileURLToPath(new URL('./enterprise-cycle-sdk-offline.mjs',import.meta.url)),configPath,
    pathToFileURL(join(resources,'general-sdk.mjs')).href],
    {cwd:workspace,env:{...process.env,PI_CODING_AGENT_DIR:agent},stdio:['pipe','pipe','pipe']});
  let output='',buffer='',errors='',watcherError;
  child.stdout.on('data',chunk=>{
    output+=chunk;buffer+=chunk;
    const lines=buffer.split('\n');buffer=lines.pop();
    for(const line of lines){try{const event=JSON.parse(line);const source=event.result?.details?.native_research_source?.source_ref;
      if(source)admitted.add(source);}catch{}}
  });
  child.stderr.on('data',chunk=>{errors+=chunk;});
  const watcher=setInterval(()=>{
    try {
      for(const name of readdirSync(join(channel,'requests')).filter(name=>name.endsWith('.json'))){
        if(seen.has(name))continue;
        const raw=readFileSync(join(channel,'requests',name),'utf8'),request=JSON.parse(raw);
        assert.equal(request.expected_revision,revision,'CAS admission uses the current committed revision');
        const changes=request.changes;
        const refs=[...(changes.notes??[]).flatMap(note=>note.refs??[]),...(changes.claims??[]).flatMap(claim=>claim.refs??[])];
        if(refs.some(ref=>!admitted.has(ref))) {
          atomic(join(channel,'receipts',name),{schema_version:'capability-research-receipt/1.0',...identity,
            status:'rejected',code:'research_reference_not_admitted',request_id:request.request_id,
            request_sha256:createHash('sha256').update(raw).digest('hex')});
          seen.add(name);continue;
        }
        for(const note of changes.notes??[]){
          const old=state?.notes.find(item=>item.note_id===note.note_id);if(old)assert.deepEqual(note,old);
        }
        for(const claim of changes.claims??[])for(const ref of claim.refs??[])assert.ok(admitted.has(ref));
        const notes=new Map((state?.notes??[]).map(note=>[note.note_id,note]));
        for(const note of changes.notes??[])notes.set(note.note_id,note);
        const claims=new Map((state?.claims??[]).map(claim=>[claim.claim_id,claim]));
        for(const claim of changes.claims??[])claims.set(claim.claim_id,claim);
        revision++;state={research_id:identity.research_id,goal:state?.goal??changes.goal,open_questions:[],...state,...changes,
          claims:[...claims.values()],notes:[...notes.values()],revision};
        for(const note of changes.notes??[])committedRevisions.set(note.note_id,revision);
        publish(); // Publish committed view before the receipt, as production.
        atomic(join(channel,'receipts',name),{schema_version:'capability-research-receipt/1.0',...identity,status:'committed',
          request_id:request.request_id,request_sha256:createHash('sha256').update(raw).digest('hex'),
          receipt:{research_id:identity.research_id,request_id:request.request_id,research_revision:revision,event_sequence:revision}});
        seen.add(name);
      }
    }catch(error){watcherError=error;child.kill('SIGTERM');}
  },5);
  child.stdin.end(JSON.stringify({type:'prompt'})+'\n');
  try {
    const code=await new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',resolve);});
    if(watcherError)throw watcherError;
    assert.equal(code,0,errors||output);
    if(scenario!=='direct-chat')assert.equal(readFileSync(join(workspace,'report.md'),'utf8'),discoveryDriven?'Total: 10\nRange: 4\n':'Total: 10\n');
    const events=output.trim().split('\n').map(line=>JSON.parse(line));
    const inventory=events.find(item=>item.type==='general_pi_inventory').tools;
    if(scenario==='split-only'||recoveryScenario||versionRecovery){
      assert.ok(!inventory.includes('agent_research_cycle'));
      for(const name of ['agent_research_plan','agent_research_record','agent_research_assess'])assert.ok(inventory.includes(name));
      const failures=events.filter(item=>item.type==='tool_execution_end'&&item.isError===true);
      for(const name of versionRecovery?['agent_research_assess']:recoveryScenario?['agent_research_record','agent_research_assess']:['agent_research_plan','agent_research_record','agent_research_assess'])assert.ok(failures.some(item=>item.toolName===name),name+' errors are real SDK errors');
      assert.equal(seen.size,versionRecovery?5:3,'rejected calls cannot create extra commits');
    }else assert.ok(inventory.includes('agent_research_cycle'));
    assert.equal(events.filter(item=>item.type==='agent_end').length,1,'Only settled final completion is public');
    if(scenario==='direct-chat'){assert.equal(state,null);assert.equal(seen.size,0);}
    else {
      assert.ok(state.notes.some(note=>note.note_id.startsWith('runtime.checkpoint.')&&JSON.parse(note.text).status===(['limited-delivery','limited-checker','producer-checkpoint'].includes(scenario)?'limited':'done')));
      assert.ok(state.claims.some(claim=>/agrees/.test(claim.statement)));
      const checkpoints=state.notes.filter(note=>note.note_id.startsWith('runtime.checkpoint.')).map(note=>JSON.parse(note.text));
      if(scenario==='producer-checkpoint'){
        const final=checkpoints.at(-1).snapshot;
        assert.equal(final.phase,'limited');assert.equal(final.pending_action,null);
        assert.equal(final.objectives.find(item=>item.id==='produce').status,'met');
        assert.equal(final.objectives.find(item=>item.id==='advisory').status,'partial');
        assert.deepEqual(final.objectives.find(item=>item.id==='handoff').depends_on,['produce']);
        assert.match(final.limitations.join('\n'),/checker and repair failed/);
        assert.deepEqual(final.delivery_products.map(item=>item.path),['report.md','metrics.csv']);
        assert.ok(!readdirSync(workspace).includes('extra-check-ran'),'producer barrier prevented the extra native command');
        const errors=events.filter(item=>item.type==='tool_execution_end'&&item.isError);
        assert.deepEqual(errors.map(item=>item.toolCallId),['extra-check','advisory-check','repair-check']);
        assert.match(JSON.stringify(events.find(item=>item.type==='agent_end').messages.at(-1).content),/checker and repair failed/);
      }
      if(scenario==='limited-checker'){
        const final=checkpoints.at(-1);assert.equal(final.status,'limited');assert.equal(final.snapshot.pending_action,null);
        assert.deepEqual(final.snapshot.delivery_products.map(item=>item.path),['report.md','metrics.csv']);
        assert.match(final.snapshot.limitations.join('\n'),/Local self-check failed/);
        assert.match(JSON.stringify(events.find(item=>item.type==='agent_end').messages.at(-1).content),/human review.*known errors/);
        assert.equal(events.filter(item=>item.type==='tool_execution_start'&&['write','edit','agent_delegate'].includes(item.toolName)).length,0,
          'usable prior outputs close without recomputation, rewrite, or compulsory review');
        assert.equal(readFileSync(join(workspace,'metrics.csv'),'utf8'),'total\n10\n');
        assert.equal(events.filter(item=>item.type==='tool_execution_start'&&item.toolName==='bash').length,1,'no checker retry loop');
      }
      if(scenario==='limited-delivery'){
        const final=checkpoints.at(-1);
        assert.equal(final.snapshot.phase,'limited');assert.equal(final.snapshot.pending_action,null);
        assert.deepEqual(final.snapshot.delivery_products.map(item=>item.path),['report.md']);
        assert.ok(final.receipts.some(item=>item.tool_name==='agent_delegate'&&item.status==='failed'&&!item.review));
        assert.match(final.snapshot.limitations.join('\n'),/report.md.*no completed independent review/);
        const terminal=events.find(item=>item.type==='agent_end');
        assert.notEqual(terminal.success,false,'a failed review does not fail the completed parent action');
        assert.match(JSON.stringify(terminal.messages.at(-1).content),/Completed with limitations/);
        assert.equal(events.filter(item=>item.type==='delegation_child_started').length,1,'no repeated child review');
      }
      if(versionRecovery){
        assert.equal(events.filter(item=>item.type==='tool_execution_start'&&item.toolName==='write').length,2,'the recovery execute verifies retained correct bytes without rewriting them');
        const branches=events.filter(item=>item.type.startsWith('delegation_child_'));
        assert.deepEqual(branches.map(item=>item.type),[
          'delegation_child_started','delegation_child_response','delegation_child_finished',
          'delegation_child_started','delegation_child_response','delegation_child_finished',
        ]);
        assert.ok(branches.every(item=>item.review_mode==='delivery'));
        for(const item of branches.filter(item=>item.type==='delegation_child_response')){
          assert.equal(item.response_number,1);
          assert.ok(Number.isInteger(item.response_ms)&&item.response_ms>=0);
        }
        const final=checkpoints.at(-1).snapshot;
        assert.equal(final.product_history.filter(item=>item.path==='report.md').length,2);
        assert.deepEqual(final.delivery_products.map(item=>item.path),['report.md']);
      }
      if(scenario==='shell-pipelines'){
        const failed=events.filter(item=>item.type==='tool_execution_end'&&item.toolName==='bash'&&item.isError);
        assert.equal(failed.length,2,'Only upstream failure and actual SIGPIPE fail');
        const receipts=checkpoints.at(-1).receipts;
        assert.equal(receipts.filter(item=>item.status==='failed').length,2,'Failed pipelines do not become successful observations');
      }
      if(scenario==='split-only')assert.equal(checkpoints.at(-1).receipts.length,2,'Only actual source read and saved report write produce execution receipts');
      assert.ok(checkpoints.some(saved=>saved.receipts.some(receipt=>receipt.status==='completed')));
      assert.ok(events.some(event=>event.type==='enterprise_cycle_progress'&&event.progress.phase==='settled'));
      if(scenario==='full-cycle')assert.ok(events.some(event=>event.type==='enterprise_cycle_progress'&&event.progress.outcome==='partial'));
      if(['automatic-work','automatic-ready-work','delegated-work'].includes(scenario)){
        const branches=events.filter(event=>event.type.startsWith('delegation_child_'));
        assert.ok(branches.some(event=>event.type==='delegation_child_started'));
        const finished=branches.find(event=>event.type==='delegation_child_finished');
        assert.equal(finished.status,'completed');
        assert.match(finished.result_summary,/independent source total is 10/);
        for(const branch of branches){
          assert.deepEqual(branch.owner,config.researchOwner);
          assert.equal(branch.attempt_id,config.researchAttemptId);
          if(automaticScenario)assert.match(branch.parent_tool_call_id,/^auto-[a-f0-9]{64}$/);
          else assert.equal(branch.parent_tool_call_id,'delegate');
          if(scenario==='automatic-ready-work')assert.match(branch.parent_step_id,/^host-ready-/);
          else assert.equal(branch.parent_step_id,'total');
          assert.deepEqual(branch.questions,['What is the source total?']);
          assert.ok(branch.expected_outputs.length);
          assert.ok(state.notes.some(note=>note.note_id===branch.checkpoint.ref));
        }
        const delegated=events.find(event=>event.type==='tool_execution_end'&&event.toolName==='agent_delegate');
        assert.equal(delegated.result.details.children[0].status,'completed');
        const checkpoint=checkpoints.find(saved=>saved.receipts.some(receipt=>receipt.ref===delegated.result.details.native_research_source.source_ref));
        assert.ok(checkpoint,'parent action stores actual child result receipt');
        const childDirs=readdirSync(join(workspace,'.research-workers'));
        if(scenario==='automatic-ready-work'){
          assert.equal(childDirs.length,2);
          const started=branches.filter(item=>item.type==='delegation_child_started');
          assert.equal(started.length,2);assert.equal(new Set(started.map(item=>item.parent_tool_call_id)).size,1);
          assert.ok(branches.findIndex(item=>item.type==='delegation_child_finished')>
            branches.findLastIndex(item=>item.type==='delegation_child_started'));
        }
        assert.equal(readFileSync(join(workspace,'.research-workers',childDirs[0],'child-result.md'),'utf8'),'Independent total: 10\n');
      }
      if(scenario==='mcp-work')assert.ok(checkpoints.some(saved=>saved.receipts.some(receipt=>receipt.ref.startsWith('execution-receipt:')&&receipt.status==='completed')));
      if(discoveryDriven){
        const branchEvents=events.filter(event=>event.type.startsWith('delegation_child_'));
        assert.equal(branchEvents.filter(event=>event.type==='delegation_child_started').length,2);
        assert.equal(branchEvents.filter(event=>event.type==='delegation_child_finished').length,2);
        assert.ok(branchEvents.findIndex(event=>event.type==='delegation_child_finished')>
          branchEvents.findLastIndex(event=>event.type==='delegation_child_started'),'Both independent children start before either finishes');
        for(const event of branchEvents){
          assert.deepEqual(event.owner,config.researchOwner);assert.equal(event.attempt_id,config.researchAttemptId);
          assert.equal(event.parent_tool_call_id,'research-delegate');assert.equal(event.parent_step_id,'research');
          assert.equal(event.questions.length,1);assert.ok(event.expected_outputs.length);
          const note=state.notes.find(note=>note.note_id===event.checkpoint.ref);
          assert.ok(note,'Branch references an actually committed checkpoint');
          assert.equal(event.checkpoint.revision,committedRevisions.get(note.note_id));
          const checkpoint=JSON.parse(note.text);
          assert.ok(checkpoint.snapshot.pending_action.questions.includes(event.questions[0]));
        }
        const planned=checkpoints.find(saved=>saved.cycleCall.id==='discovery-assess').snapshot;
        if(scenario==='discovery-branches')assert.equal(planned.objectives.find(item=>item.id==='obsolete-report').status,'superseded');
        else if(scenario==='adoption-branches'){
          const initial=checkpoints.find(saved=>saved.cycleCall.id==='discovery-plan').snapshot;
          assert.deepEqual(initial.objectives.find(item=>item.id==='research').questions,['What is the source total?']);
          assert.deepEqual(planned.last_assessment.follow_ups,[],'Adoption changes an existing pending objective instead of adding a replacement');
          assert.deepEqual(planned.question_adoptions,[{objective_id:'research',questions:['What is the source range?'],derived_from:['source-discovery'],
            assessment_action_id:checkpoints.find(saved=>saved.cycleCall.id==='discovery-record').snapshot.pending_action.id,round:1}]);
          const rangeBranch=branchEvents.find(event=>event.type==='delegation_child_started'&&event.child_id==='range-branch');
          assert.deepEqual(rangeBranch.questions,['What is the source range?']);
          assert.equal(rangeBranch.parent_action_id,planned.pending_action.id,'The adopted question is admitted under the committed updated action');
        }else {
          const initial=checkpoints.find(saved=>saved.cycleCall.id==='discovery-plan').snapshot;
          assert.deepEqual(initial.objectives.find(item=>item.id==='total-analysis').depends_on,['discover']);
          assert.deepEqual(initial.objectives.find(item=>item.id==='range-analysis').depends_on,['discover']);
          const record=events.find(event=>event.type==='tool_execution_end'&&event.toolCallId==='discovery-record');
          assert.deepEqual(record.result.details.result.planning_context.ready_if_current_met.map(item=>item.id),['total-analysis','range-analysis']);
          for(const id of ['total-analysis','range-analysis']){
            const original=initial.objectives.find(item=>item.id===id),superseded=planned.objectives.find(item=>item.id===id);
            assert.equal(superseded.status,'superseded');assert.deepEqual(superseded.supersession.replacement_ids,['research']);
            assert.ok(original.questions.every(question=>planned.pending_action.questions.includes(question)),'Combined action retains member question scope');
          }
          assert.deepEqual(planned.objectives.find(item=>item.id==='research').depends_on,['discover'],'Combination retains its external prerequisite');
        }
        const research=planned.objectives.find(item=>item.id==='research');
        assert.deepEqual(research.derived_from,['source-discovery']);assert.equal(research.questions.length,2);
        assert.equal(planned.pending_action.objective_id,'research');
        assert.match(planned.last_assessment.reflection.next_step_reason,/two independently/);
        const integrated=checkpoints.find(saved=>saved.cycleCall.id==='research-record');
        const delegate=events.find(event=>event.type==='tool_execution_end'&&event.toolName==='agent_delegate');
        assert.ok(integrated.receipts.some(receipt=>receipt.ref===delegate.result.details.native_research_source.source_ref&&receipt.action_id===planned.pending_action.id));
        for(const child of delegate.result.details.children){
          const finish=branchEvents.find(event=>event.type==='delegation_child_finished'&&event.child_id===child.source.id);
          assert.equal(finish.status,'completed');assert.equal(finish.result_summary,child.answer);
        }
        assert.equal(readdirSync(join(workspace,'.research-workers')).length,2);
        assert.match(readFileSync(join(workspace,'integration.md'),'utf8'),/Independent total: 10/);
        assert.match(readFileSync(join(workspace,'integration.md'),'utf8'),/Independent range: 4/);
        const next=checkpoints.find(saved=>saved.cycleCall.id==='research-assess').snapshot;
        assert.deepEqual(next.pending_action.derived_from,scenario==='ready-batch'?[]:['branch-result']);
        assert.equal(next.pending_action.objective_id,'final-report');
        if(scenario==='ready-batch'){
          assert.deepEqual(next.last_assessment.follow_ups,[],'Existing downstream work activates without being recreated');
          assert.deepEqual(next.objectives.find(item=>item.id==='final-report').depends_on,['total-analysis','range-analysis']);
        }
        const settled=events.filter(event=>event.type==='enterprise_cycle_progress'&&event.progress.phase==='settled');
        assert.equal(settled.length,3);
        const researchStep=settled.find(event=>event.progress.step_id==='research').progress;
        assert.equal(researchStep.text,'Answer the discovered independent questions');
        assert.match(researchStep.result_summary,/Actual child total and range/);
        assert.ok(!events.some(event=>event.progress?.step_id==='obsolete-report'),'Replacing unexecuted work creates no fictional execution step');
      }
    }
  }finally{clearInterval(watcher);child.kill('SIGTERM');rmSync(dir,{recursive:true,force:true});}
});
