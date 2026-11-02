// Real SDK/tool/session lifecycle; only model responses are scripted offline.
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const config=JSON.parse(readFileSync(process.argv[2],'utf8'));
const automaticScenario=config.fixtureScenario.startsWith('automatic-');
const discoveryDriven=['discovery-branches','adoption-branches','ready-batch'].includes(config.fixtureScenario);
const recoveryScenario=['state-recovery','long-state-recovery'].includes(config.fixtureScenario);
const recoveryQuestion=config.fixtureScenario==='long-state-recovery'?'What is the source total? '+'Q'.repeat(70000):'What is the source total?';
const sdk=await import(pathToFileURL(config.sdk).href);
const ai=await import(pathToFileURL(resolve(dirname(config.sdk),'../../ai/dist/index.js')).href);
const {runManagedSession}=await import(process.argv[3]);
const model={id:config.model,name:'Offline actual SDK cycle',provider:'capstone-general',api:'openai-completions',
  baseUrl:'http://127.0.0.1:1',reasoning:false,input:['text'],contextWindow:64000,maxTokens:4096,
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let turn=0,childTurns=0;
const childTurnsByDirectory=new Map();
const tool=(id,name,args)=>({type:'toolCall',id,name,arguments:args});
const modelRuntime={getModel:()=>model,hasConfiguredAuth:()=>true,getAuth:async()=>({auth:{apiKey:'offline-fixture'}}),isUsingOAuth:()=>false,
  streamSimple(_model,context) {
    const results=context.messages.filter(item=>item.role==='toolResult');
    const previous=id=>results.find(item=>item.toolCallId===id);
    const objective={id:'total',purpose:'Calculate and verify source total',questions:[recoveryScenario?recoveryQuestion:'What is the source total?'],depends_on:[],expected_outputs:['report.md'],checks:['sum'],mode:'execute',input_refs:[],resolves:[]};
    const plan={operation:'plan',goal:'Deliver correct CSV total',output_mode:'files',objectives:[objective],source_refs:['material:source']};
    const details=id=>JSON.parse(previous(id).content[0].text);
    const ref=id=>JSON.stringify(previous(id).content).match(/native-observation:task-sdk:[a-f0-9]{64}/)[0];
    const record=(id,actionId,findingId,text,readId)=>tool(id,'agent_research_cycle',{operation:'record',action_id:actionId,outcome:'completed',
      findings:[{id:findingId,text,status:'supported',refs:[ref(readId)]}],product_refs:['report.md'],limitations:[]});
    const assessment=(id,actionId,objectiveId,decision,readId)=>tool(id,'agent_research_cycle',{operation:'assess',action_id:actionId,
      coverage:[{objective_id:objectiveId,status:decision==='revise'?'partial':'met',refs:[ref(readId)],explanation:decision==='revise'?'Report 9 differs from source 10':'Report agrees with source'}],
      checks:[{description:'sum',status:decision==='revise'?'failed':'passed',refs:[ref(readId)],explanation:'Compared actual saved bytes against source total'}],
      decision,summary:decision==='revise'?'Repair the affected total in report.md':'Actual saved report total agrees with source 10',
      follow_ups:decision==='revise'?[{...objective,id:'repair',purpose:'Repair the affected total in report.md',resolves:['total']}]:[]});
    let content;
    const isReviewChild=['review-version-recovery','limited-delivery'].includes(config.fixtureScenario)&&JSON.stringify(context.messages[0]?.content).includes('capstone-delivery-review-packet/1');
    const isChild=isReviewChild||JSON.stringify(context.messages[0]?.content).includes('Your output directory:');
    if(isReviewChild){
      assert.deepEqual(context.tools,[]);assert.equal(context.messages.length,1);
      const prompt=JSON.stringify(context.messages[0].content),wrong=prompt.includes('Total: 9');
      content=[{type:'text',text:JSON.stringify({summary:'Compared actual supplied report and source.csv rows.',findings:wrong?[{severity:'blocking',path:'report.md',description:'Saved total 9 disagrees with source rows 3 and 7; verify before editing.'}]:[],not_checked:['No visual inspection.']})}];
    }else if(isChild){
      const prompt=context.messages[0].content.filter(item=>item.type==='text').map(item=>item.text).join('\n');
      if(config.fixtureScenario==='delegated-work'){
        assert.doesNotMatch(context.systemPrompt,/PARENT_WORKFLOW_SENTINEL|SOURCE_MANIFEST_SENTINEL/);
        assert.match(context.systemPrompt,/untrusted/);assert.match(context.systemPrompt,/Authority/);
        assert.match(context.systemPrompt,/external lookup/);
        assert.ok(prompt.includes(config.fixtureSourcePath),'the parent selects the actual authorized source path');
      }
      const directory=prompt.match(/Your output directory: (.+?)\. /)[1];
      assert.ok(existsSync(directory),'the child output directory must exist');
      const childTurn=childTurnsByDirectory.get(directory)??0;
      const questions=JSON.parse(prompt.match(/Accepted research questions: (\[[^\n]+\])/)[1]);
      const range=discoveryDriven&&questions.includes('What is the source range?');
      const kind=range?'range':'total',path=discoveryDriven?`child-${kind}.md`:'child-result.md';
      if(recoveryScenario)assert.ok(prompt.includes('Accepted research questions: '+JSON.stringify([recoveryQuestion])));
      else assert.match(prompt,range?/Accepted research questions: \["What is the source range\?"\]/:/Accepted research questions: \["What is the source total\?"\]/);
      if(!discoveryDriven)assert.match(prompt,/Expected results: \["Verified source total and child-result.md"\]/);
      else assert.ok(prompt.includes(`Expected results: ["Independent ${kind} and ${path}"]`));
      const values=readFileSync(config.fixtureSourcePath??'source.csv','utf8').trim().split('\n').slice(1).map(Number);
      const value=range?Math.max(...values)-Math.min(...values):values.reduce((sum,item)=>sum+item,0);
      const product=`Independent ${kind}: ${value}\n`;
      if(childTurn===0)content=[tool('child-read','read',{path:config.fixtureSourcePath??resolve(process.cwd(),'source.csv')})];
      else if(childTurn===1)content=[tool('child-write','write',{path,content:product})];
      else if(childTurn===2){assert.equal(readFileSync(resolve(directory,path),'utf8'),product);
        content=[{type:'text',text:(discoveryDriven?product+`Saved ${path}.`:'The independent source total is '+value+'. Saved child-result.md.')+
          (automaticScenario?' Retained observation.'.repeat(1500):'')}];}
      else throw Error('Child did not terminate');
      childTurnsByDirectory.set(directory,childTurn+1);
      childTurns++;
    }else if(discoveryDriven){
      const adopting=config.fixtureScenario==='adoption-branches';
      const combining=config.fixtureScenario==='ready-batch';
      const discovery={...objective,id:'discover',purpose:'Inspect actual source to identify research questions',questions:['What needs independent investigation?'],checks:['inspect-source'],expected_outputs:['Source profile']};
      const research={...objective,id:'research',purpose:'Answer the discovered independent questions',questions:['What is the source total?','What is the source range?'],
        expected_outputs:['Independent source findings','integration.md'],checks:['compare-branches'],derived_from:['source-discovery'],
        depends_on:combining?['discover']:[]};
      const report={...objective,id:'final-report',purpose:'Explain the integrated verified findings',questions:['How should the findings be explained?'],checks:['report-agreement'],
        depends_on:combining?['total-analysis','range-analysis']:['research'],derived_from:combining?[]:['branch-result']};
      const independent=research.questions.map((question,index)=>({...research,id:index===0?'total-analysis':'range-analysis',
        questions:[question],depends_on:['discover'],derived_from:[],checks:research.checks}));
      const assess=(id,previousId,obj,readId,decision,extra={})=>tool(id,'agent_research_cycle',{operation:'assess',action_id:details(previousId).pending_action.id,
        coverage:[{objective_id:obj.id,status:'met',refs:[ref(readId)],explanation:'Actual observed outcome satisfies this objective'}],
        checks:[{description:obj.checks[0],status:'passed',refs:[ref(readId)],explanation:'Checked actual source or integrated output'}],
        decision,summary:'Observed outcome is ready',follow_ups:[],...extra});
      const branchReport=()=>{
        const children=details('research-delegate').children;assert.equal(children.length,2);
        assert.ok(children.every(child=>child.status==='completed'));
        const total=children.find(child=>child.source.id==='total-branch').answer.match(/Independent total: (\d+)/)[1];
        const range=children.find(child=>child.source.id==='range-branch').answer.match(/Independent range: (\d+)/)[1];
        return `Total: ${total}\nRange: ${range}\n`;
      };
      if(turn===0)content=[tool('discovery-plan','agent_research_cycle',{...plan,goal:'Discover source questions and deliver integrated findings',objectives:combining?
        [discovery,...independent,report]:[discovery,adopting?{...research,questions:[research.questions[0]],derived_from:[],depends_on:['discover']}:
          {...objective,id:'obsolete-report',purpose:'Write a report before source discovery',depends_on:['discover']} ]})];
      else if(turn===1)content=[tool('discovery-read','read',{path:'source.csv'})];
      else if(turn===2)content=[tool('discovery-record','agent_research_cycle',{operation:'record',action_id:details('discovery-plan').pending_action.id,outcome:'completed',
        findings:[{id:'source-discovery',text:'Actual source contains two distinct values; their aggregate and spread need independent investigation',status:'supported',refs:[ref('discovery-read')]}],product_refs:[],limitations:[]})];
      else if(turn===3){
        if(combining)assert.deepEqual(details('discovery-record').planning_context.ready_if_current_met.map(item=>item.id),independent.map(item=>item.id));
        content=[assess('discovery-assess','discovery-record',discovery,'discovery-read','continue',{
        summary:'Source discovery motivates independent aggregate and spread checks',follow_ups:adopting?[]:[research],
        reflection:{discoveries:['source-discovery'],unresolved_questions:research.questions.map(question=>({question,derived_from:['source-discovery']})),next_step_reason:'Investigate two independently discovered source questions before reporting'},
        ...(adopting?{question_adoptions:[{objective_id:'research',questions:[research.questions[1]],derived_from:['source-discovery']}]}:
          {supersedes:(combining?independent:[{id:'obsolete-report'}]).map(item=>({objective_id:item.id,reason:'Combine independent accepted questions under one parent research purpose',replacement_ids:['research']}))}),
      })];}
      else if(turn===4){assert.deepEqual(details('discovery-assess').pending_action.questions,research.questions);
        content=[tool('research-delegate','agent_delegate',{tasks:[
          {id:'total-branch',title:'Independent aggregate',questions:[research.questions[0]],expected_outputs:['Independent total and child-total.md'],instruction:'Read source.csv in the shared workspace. Calculate its total and save child-total.md in your output directory.'},
          {id:'range-branch',title:'Independent spread',questions:[research.questions[1]],expected_outputs:['Independent range and child-range.md'],instruction:'Read source.csv in the shared workspace. Calculate maximum minus minimum and save child-range.md in your output directory.'},
        ]})];}
      else if(turn===5){branchReport();content=[tool('integrate','write',{path:'integration.md',content:details('research-delegate').children.map(child=>child.answer).join('\n')})];}
      else if(turn===6)content=[tool('research-record','agent_research_cycle',{operation:'record',action_id:details('discovery-assess').pending_action.id,outcome:'completed',
        findings:[{id:'branch-result',text:'Actual independent total and range agree with the integrated source observations',status:'supported',refs:[ref('research-delegate')]}],product_refs:['integration.md'],limitations:[]})];
      else if(turn===7)content=[assess('research-assess','research-record',research,'research-delegate','continue',{
        summary:'Actual child total and range are integrated into the saved source comparison',follow_ups:combining?[]:[report],
        reflection:{discoveries:['branch-result'],next_step_reason:'Prepare the final explanation from the actual independent results'}})];
      else if(turn===8)content=[tool('final-write','write',{path:'report.md',content:branchReport()})];
      else if(turn===9)content=[tool('final-read','read',{path:'report.md'})];
      else if(turn===10)content=[record('final-record',details('research-assess').pending_action.id,'final-agreement','Final saved report agrees with the actual child findings','final-read')];
      else if(turn===11)content=[assess('final-assess','final-record',report,'final-read','deliver',{summary:'Final report agrees with actual independently computed source results'})];
      else if(turn===12){assert.equal(details('final-assess').status,'done');assert.equal(readFileSync('report.md','utf8'),branchReport());
        content=[{type:'text',text:'Independent source questions were investigated and integrated into report.md.'}];}
      else throw Error('Discovery-driven research did not terminate');
    }else if(config.fixtureScenario==='shell-pipelines') {
      const commands=[['false | tail -n 1',true],["printf normal | tail -n 1",false],
        ['false | tail -n 1 || printf recovered',false],["printf 'Traceback: ordinary text'",false],
        ['yes data | head -n 1',true],['false; printf continued',false]];
      assert.match(context.systemPrompt,/pipefail/);
      assert.match(context.systemPrompt,/current model cannot inspect image content/);
      if(turn===0)content=[tool('plan','agent_research_cycle',plan)];
      else if(turn<=commands.length){
        if(turn>1)assert.equal(previous('shell-'+(turn-2)).isError,commands[turn-2][1]);
        content=[tool('shell-'+(turn-1),'bash',{command:commands[turn-1][0]})];
      }else if(turn===7){assert.equal(previous('shell-5').isError,false);content=[tool('write-report','write',{path:'report.md',content:'Total: 10\n'})];}
      else if(turn===8)content=[record('record',details('plan').pending_action.id,'correct','Actual normal shell execution agrees with saved report','shell-1')];
      else if(turn===9)content=[assessment('assess',details('record').pending_action.id,'total','deliver','shell-1')];
      else if(turn===10){assert.equal(details('assess').status,'done');content=[{type:'text',text:'Shell pipeline status preserved in the actual parent session.'}];}
      else throw Error('Shell pipeline fixture did not terminate');
    }else if(config.fixtureScenario==='producer-checkpoint') {
      const produce={...objective,id:'produce',purpose:'Produce the requested core files',checks:['Core files saved'],product_paths:['report.md','metrics.csv']};
      const advisory={...objective,id:'advisory',purpose:'Find and record advisory problems',depends_on:['produce'],checks:['Advisory consistency']};
      const handoff={...objective,id:'handoff',purpose:'Return files and known errors for human review',depends_on:['produce'],checks:[]};
      const assessFor=(id,previousId,item,decision,status='met')=>tool(id,'agent_research_cycle',{operation:'assess',action_id:details(previousId).pending_action.id,
        coverage:[{objective_id:item.id,status,refs:status==='met'?[ref('produce')]:[],explanation:'Actual saved files retained; no clean quality claim'}],
        checks:item.checks.map(description=>({description,status:status==='met'?'passed':'failed',refs:status==='met'?[ref('produce')]:[],explanation:'Actual observation or retained checker failure'})),
        decision,summary:status==='met'?'Core files saved, not quality-certified.':'Local checker and repair failed; continue with known errors.',follow_ups:[],
        ...(decision==='limited'?{delivery_product_refs:['report.md','metrics.csv']}:{})});
      if(turn===0)content=[tool('plan','agent_research_cycle',{...plan,objectives:[produce,advisory,handoff]})];
      else if(turn===1)content=[tool('produce','bash',{command:"printf 'Total: 10\\n' > report.md; printf 'total\\n10\\n' > metrics.csv; printf 'Core files saved\\n'"})];
      else if(turn===2){
        assert.equal(previous('produce').isError,false);
        assert.match(JSON.stringify(previous('produce').content),/Core files saved.*Observed producer output checkpoint/);
        assert.ok(JSON.stringify(previous('produce').content).includes(details('plan').pending_action.id));
        content=[tool('extra-check','bash',{command:'printf should-not-run > extra-check-ran'})];
      }
      else if(turn===3){assert.equal(previous('extra-check').isError,true);
        const text=JSON.stringify(previous('extra-check').content);assert.match(text,/Observed producer output checkpoint/);
        assert.ok(text.includes(details('plan').pending_action.id));assert.match(text,/sha256/);
        assert.ok(!existsSync('extra-check-ran'));
        content=[tool('record-produced','agent_research_cycle',{operation:'record',action_id:details('plan').pending_action.id,outcome:'completed',
          findings:[{id:'saved-core',text:'Saved output agrees with the observed file production; quality remains unchecked.',status:'supported',refs:[ref('produce')]}],product_refs:produce.product_paths,limitations:['Advisory quality checking not yet completed.']})];
      }else if(turn===4)content=[assessFor('assess-produced','record-produced',produce,'continue')];
      else if(turn===5){assert.equal(details('assess-produced').pending_action.objective_id,'advisory');content=[tool('advisory-check','bash',{command:"printf 'advisory checker failed\\n'; exit 1"})];}
      else if(turn===6)content=[tool('repair-check','bash',{command:"printf 'attempted repair failed\\n'; exit 2"})];
      else if(turn===7)content=[tool('record-advisory','agent_research_cycle',{operation:'record',action_id:details('assess-produced').pending_action.id,outcome:'failed',findings:[],product_refs:[],limitations:['Local checker and repair failed; usable core files remain.']})];
      else if(turn===8)content=[assessFor('assess-advisory','record-advisory',advisory,'continue','partial')];
      else if(turn===9){assert.equal(details('assess-advisory').pending_action.objective_id,'handoff');content=[tool('handoff-read','read',{path:'report.md'})];}
      else if(turn===10)content=[tool('record-handoff','agent_research_cycle',{operation:'record',action_id:details('assess-advisory').pending_action.id,outcome:'limited',findings:[],product_refs:[],limitations:['Known checker and repair failures retained for human review.']})];
      else if(turn===11)content=[assessFor('assess-handoff','record-handoff',handoff,'limited','partial')];
      else if(turn===12){assert.equal(details('assess-handoff').status,'limited');content=[{type:'text',text:'Draft files retained for human review. Local checker and repair failed; these warnings remain unresolved. [Report](report.md), [metrics](metrics.csv).'}];}
      else throw Error('Producer checkpoint did not finish');
    }else if(config.fixtureScenario==='limited-checker') {
      if(turn===0)content=[tool('plan','agent_research_cycle',plan)];
      else if(turn===1)content=[tool('existing-report','read',{path:'report.md'})];
      else if(turn===2)content=[tool('local-check','bash',{command:"printf 'Local self-check failed: optional literal registration incomplete\\n'; exit 1"})];
      else if(turn===3){assert.equal(previous('local-check').isError,true);
        assert.match(JSON.stringify(previous('local-check').content),/Host closure guidance.*usable draft.*human review/);
        assert.ok(JSON.stringify(previous('local-check').content).includes(details('plan').pending_action.id));
        content=[tool('record-limited','agent_research_cycle',{operation:'record',action_id:details('plan').pending_action.id,outcome:'limited',
          findings:[{id:'retained-draft',text:'Retained draft agrees with the bytes actually read; quality remains unchecked.',status:'supported',refs:[ref('existing-report')]}],
          product_refs:['report.md','metrics.csv'],limitations:['Local self-check failed: optional literal registration incomplete; numbers not independently verified.']})];
      }else if(turn===4)content=[tool('limited','agent_research_cycle',{operation:'assess',action_id:details('record-limited').pending_action.id,
        coverage:[{objective_id:'total',status:'partial',refs:[ref('existing-report')],explanation:'Existing readable draft retained for human feedback'}],
        checks:[{description:'sum',status:'failed',refs:[],explanation:'Local self-check failed; independent check not run'}],decision:'limited',
        summary:'Existing draft supplied for human review with known errors.',follow_ups:[],delivery_product_refs:['report.md','metrics.csv']})];
      else if(turn===5){assert.equal(details('limited').status,'limited');assert.equal(details('limited').pending_action,null);
        content=[{type:'text',text:'Completed draft for human review with known errors. [Report](report.md) and [metrics](metrics.csv) retained unchanged. Local checker failed; numerical checks and independent review remain incomplete.'}];
      }else throw Error('Checker advisory closure did not terminate');
    }else if(config.fixtureScenario==='limited-delivery') {
      if(turn===0)content=[tool('plan','agent_research_cycle',plan)];
      else if(turn===1)content=[tool('source-read','read',{path:'source.csv'})];
      else if(turn===2)content=[tool('write-report','write',{path:'report.md',content:'Total: 10\n'})];
      else if(turn===3)content=[record('record',details('plan').pending_action.id,'correct','Actual saved total agrees with source','source-read')];
      else if(turn===4)content=[tool('review','agent_delegate',{tasks:[{id:'one-review',title:'Check actual saved report',instruction:'Compare report.md with source.csv; state unchecked scope.',questions:objective.questions,expected_outputs:['Discrepancies and limits']}],review_products:['report.md','source.csv']})];
      else if(turn===5){assert.equal(previous('review').isError,true);content=[assessment('clean-delivery',details('record').pending_action.id,'total','deliver','source-read')];}
      else if(turn===6){assert.equal(previous('clean-delivery').details.error.code,'delivery_review_required');
        assert.match(JSON.stringify(previous('clean-delivery').content),/partial.*limited/);
        content=[tool('limited','agent_research_cycle',{operation:'assess',action_id:details('record').pending_action.id,
          coverage:[{objective_id:'total',status:'partial',refs:[ref('source-read')],explanation:'Report retained; independent review failed'}],
          checks:[{description:'sum',status:'not_run',refs:[],explanation:'Independent review did not complete'}],decision:'limited',
          summary:'Usable report retained; no clean independent review is claimed.',follow_ups:[],delivery_product_refs:['report.md']})];
      }else if(turn===7){assert.equal(details('limited').status,'limited');assert.equal(details('limited').pending_action,null);
        assert.match(details('limited').limitations.join('\n'),/report.md.*no completed independent review/);
        assert.equal(details('limited').delivery_review.ready,false);
        content=[{type:'text',text:'Completed with limitations. [Saved report](report.md) is available. Independent review failed; its checks remain unresolved.'}];
      }else throw Error('Limited delivery did not terminate');
    }else if(config.fixtureScenario==='review-version-recovery') {
      const strip=({operation,...args})=>args;
      const review=id=>tool(id,'agent_delegate',{tasks:[{id,title:'Read actual report and source',instruction:'Compare saved report with source.csv and return structured findings.',questions:objective.questions,expected_outputs:['Observed discrepancies']}],review_products:['report.md','source.csv']});
      if(turn===0)content=[tool('plan','agent_research_plan',strip(plan))];
      else if(turn===1)content=[tool('source-read','read',{path:'source.csv'})];
      else if(turn===2)content=[tool('write-v1','write',{path:'report.md',content:'Total: 9\n'})];
      else if(turn===3)content=[tool('record-v1','agent_research_record',strip(record('unused',details('plan').pending_action.id,'observed-v1','Recorded report 9 for comparison with the supplied source','source-read').arguments))];
      else if(turn===4)content=[review('review-v1')];
      else if(turn===5){assert.equal(previous('review-v1').details.delivery_review.findings.length,1);content=[tool('correct-after-record','write',{path:'report.md',content:'Total: 10\n'})];}
      else if(turn===6)content=[tool('stale-deliver','agent_research_assess',{...strip(assessment('unused',details('record-v1').pending_action.id,'total','deliver','source-read').arguments),delivery_product_refs:['report.md']})];
      else if(turn===7){
        assert.equal(previous('stale-deliver').isError,true);const error=previous('stale-deliver').details.error;
        assert.equal(error.code,'research_product_version_mismatch');const mismatch=error.product_mismatches.products[0];
        assert.equal(mismatch.reason,'changed_version');assert.notEqual(mismatch.registered_sha256,mismatch.current_sha256);
        assert.match(JSON.stringify(previous('stale-deliver').content),/partial.*revise.*resolves/);
        content=[tool('revise','agent_research_assess',strip(assessment('unused',details('record-v1').pending_action.id,'total','revise','source-read').arguments))];
      }else if(turn===8){assert.equal(details('revise').phase,'executing');assert.equal(readFileSync('report.md','utf8'),'Total: 10\n');content=[tool('verify-current','read',{path:'report.md'})];}
      else if(turn===9)content=[tool('record-v2','agent_research_record',strip(record('unused',details('revise').pending_action.id,'observed-v2','Verified retained report total agrees with source 10','verify-current').arguments))];
      else if(turn===10)content=[review('review-v2')];
      else if(turn===11){assert.equal(previous('review-v2').details.delivery_review.findings.length,0);content=[tool('deliver','agent_research_assess',{...strip(assessment('unused',details('record-v2').pending_action.id,'repair','deliver','verify-current').arguments),delivery_product_refs:['report.md']})];}
      else if(turn===12){assert.equal(details('deliver').status,'done');content=[{type:'text',text:'Verified retained current report, registered new bytes and independently reviewed the final version.'}];}
      else throw Error('Version recovery did not terminate');
    }else if(recoveryScenario) {
      if(config.fixtureScenario==='long-state-recovery'&&turn>0){
        const summary=context.messages.find(message=>JSON.stringify(message.content).includes('Committed research state (agent judgments'));
        const text=typeof summary.content==='string'?summary.content:summary.content.find(part=>part.type==='text').text;
        assert.ok(Array.from(text).length<=65536);const compact=JSON.parse(text.slice(text.indexOf('\n')+1)).cycle;
        if(turn<12){assert.equal(compact.coverage.omitted.questions,1);assert.equal(compact.coverage.omitted.question_chars,recoveryQuestion.length);
          assert.ok(!Object.hasOwn(compact.pending_action,'questions'));}
      }
      const strip=({operation,...args})=>args;
      if(turn===0)content=[tool('plan','agent_research_plan',strip(plan))];
      else if(turn===1)content=[tool('source-read','read',{path:'source.csv'})];
      else if(turn===2)content=[tool('bad-record','agent_research_record',{...strip(record('unused',details('plan').pending_action.id,'correct','Actual source agrees','source-read').arguments),action_id:'cycle-'+'a'.repeat(64)})];
      else if(turn===3){assert.equal(previous('bad-record').isError,true);assert.equal(previous('bad-record').details.error.action_mismatch.expected_action_id,details('plan').pending_action.id);content=[tool('recover-execute','agent_research_read',{section:'overview'})];}
      else if(turn===4){
        const overview=details('recover-execute');assert.deepEqual(overview.cycle.pending_action,details('plan').pending_action);
        assert.deepEqual(overview.open_questions,[]);assert.ok(overview.cycle.pending_action.questions.length);
        assert.ok(!JSON.stringify(overview.notes).includes('runtime.checkpoint.'));
        content=[tool('bad-delegate','agent_delegate',{tasks:[{id:'bad',title:'Unaccepted question',instruction:'Read source.csv',questions:['Invented unaccepted question'],expected_outputs:['Source total']}]} )];
      }else if(turn===5){assert.equal(previous('bad-delegate').isError,true);content=[tool('recover-questions','agent_research_read',{section:'overview'})];}
      else if(turn===6){const action=details('recover-questions').cycle.pending_action;content=[tool('delegate','agent_delegate',{tasks:[{id:'independent-total',title:'Verify source total',instruction:'Read source.csv and save child-result.md with the actual total.',questions:action.questions,expected_outputs:['Verified source total and child-result.md']}]} )];}
      else if(turn===7){assert.equal(previous('delegate').isError,false);content=[tool('write-report','write',{path:'report.md',content:'Total: 10\n'})];}
      else if(turn===8)content=[tool('record','agent_research_record',strip(record('unused',details('recover-execute').cycle.pending_action.id,'correct','Actual source total agrees with report 10','source-read').arguments))];
      else if(turn===9)content=[tool('bad-assess','agent_research_assess',strip(assessment('unused',details('plan').pending_action.id,'total','deliver','source-read').arguments))];
      else if(turn===10){assert.equal(previous('bad-assess').isError,true);assert.equal(previous('bad-assess').details.error.action_mismatch.expected_action_id,details('record').pending_action.id);content=[tool('recover-assess','agent_research_read',{section:'overview'})];}
      else if(turn===11){const cycle=details('recover-assess').cycle;assert.equal(cycle.phase,'assessing');assert.equal(cycle.pending_action.id,details('record').pending_action.id);assert.notEqual(cycle.pending_action.id,details('plan').pending_action.id);
        const summaries=context.messages.filter(message=>JSON.stringify(message.content).includes('Committed research state (agent judgments'));
        assert.equal(summaries.length,1);assert.ok(JSON.stringify(summaries[0]).includes(cycle.pending_action.id));
        assert.deepEqual(Object.keys(cycle).sort(),['checkpoint','next_action','pending_action','phase','round','update_pending']);
        content=[tool('assess','agent_research_assess',strip(assessment('unused',cycle.pending_action.id,'total','deliver','source-read').arguments))];}
      else if(turn===12){assert.equal(details('assess').status,'done');content=[{type:'text',text:'Recovered exact current action and accepted questions without changing state.'}];}
      else throw Error('State recovery did not terminate');
    }else if(config.fixtureScenario==='split-only') {
      const strip=({operation,...args})=>args;
      if(turn===0){
        for(const name of ['agent_research_plan','agent_research_record','agent_research_assess']){
          const advertised=context.tools.find(item=>item.name===name);
          assert.ok(advertised,name+' is registered in the actual SDK');
          assert.equal(advertised.parameters.type,'object');
          assert.ok(!Object.hasOwn(advertised.parameters.properties,'operation'));
        }
        assert.ok(!context.tools.some(item=>item.name==='agent_research_cycle'));
        content=[tool('bad-plan','agent_research_plan',{...strip(plan),operation:'plan'})];
      }else if(turn===1){assert.equal(previous('bad-plan').isError,true);content=[tool('plan','agent_research_plan',strip(plan))];}
      else if(turn===2){assert.match(details('plan').next_action,/agent_research_record/);content=[tool('plan','agent_research_plan',strip(plan))];}
      else if(turn===3)content=[tool('plan','agent_research_record',{action_id:details('plan').pending_action.id,outcome:'completed',findings:[],product_refs:[],limitations:[]})];
      else if(turn===4){assert.equal(results.at(-1).isError,true);assert.match(JSON.stringify(results.at(-1).content),/identity changed/);content=[tool('source-read','read',{path:'source.csv'})];}
      else if(turn===5)content=[tool('write-report','write',{path:'report.md',content:'Total: 10\n'})];
      else if(turn===6)content=[tool('bad-record','agent_research_record',{...strip(record('unused',details('plan').pending_action.id,'correct','Actual source agrees','source-read').arguments),operation:'record'})];
      else if(turn===7){assert.equal(previous('bad-record').isError,true);content=[tool('record','agent_research_record',strip(record('unused',details('plan').pending_action.id,'correct','Actual source total agrees with report 10','source-read').arguments))];}
      else if(turn===8){assert.match(details('record').next_action,/agent_research_assess/);content=[tool('bad-assess','agent_research_assess',{...strip(assessment('unused',details('record').pending_action.id,'total','deliver','source-read').arguments),operation:'assess'})];}
      else if(turn===9){assert.equal(previous('bad-assess').isError,true);content=[tool('assess','agent_research_assess',strip(assessment('unused',details('record').pending_action.id,'total','deliver','source-read').arguments))];}
      else if(turn===10){assert.equal(details('assess').status,'done');assert.equal(readFileSync('report.md','utf8'),'Total: 10\n');content=[{type:'text',text:'Split control protocol delivered the actual total 10.'}];}
      else throw Error('Split research did not terminate');
    }else if(config.fixtureScenario==='direct-chat') {
      assert.equal(turn,0,'Untouched chat has no research continuation');content=[{type:'text',text:'A direct conversational answer.'}];
    }else if(config.fixtureScenario==='mcp-work') {
      if(turn===0)content=[tool('unplanned-mcp','source_total',{})];
      else if(turn===1){assert.equal(previous('unplanned-mcp').isError,true);content=[tool('plan','agent_research_cycle',plan)];}
      else if(turn===2)content=[tool('lookup','source_total',{})];
      else if(turn===3){assert.equal(JSON.parse(previous('lookup').content[0].text).total,10);content=[tool('report','write',{path:'report.md',content:'Total: 10\n'})];}
      else if(turn===4)content=[tool('record','agent_research_cycle',{operation:'record',action_id:details('plan').pending_action.id,outcome:'completed',findings:[{id:'total',text:'Actual lookup total agrees with report 10',status:'supported',refs:['material:source']}],product_refs:['report.md'],limitations:[]})];
      else if(turn===5)content=[tool('assess','agent_research_cycle',{operation:'assess',action_id:details('record').pending_action.id,coverage:[{objective_id:'total',status:'met',refs:['material:source'],explanation:'Compared source values'}],checks:[{description:'sum',status:'passed',refs:['material:source'],explanation:'Actual lookup total 10 agrees'}],decision:'deliver',summary:'Actual total agrees',follow_ups:[]})];
      else if(turn===6){assert.equal(details('assess').status,'done');content=[{type:'text',text:'Authorized MCP total 10 saved in report.md.'}];}
      else throw Error('MCP research did not terminate');
    }else if(automaticScenario) {
      if(turn===0){
        const childObjective=id=>({...objective,id,subtasks:[{
          id:'independent-total',title:'Independent total',instruction:'Read '+resolve('source.csv')+' and save child-result.md.',
          questions:objective.questions,expected_outputs:['Verified source total and child-result.md'],depends_on:[]}]});
        content=[tool('plan','agent_research_cycle',{...plan,objectives:config.fixtureScenario==='automatic-ready-work'?
          [childObjective('total'),childObjective('verify')]:[childObjective('total')]})];
      }
      else if(turn===1){
        const delegated=details('plan').delegation;
        assert.equal(delegated.details.children[0].status,'completed');
        assert.match(delegated.details.children[0].answer,/10/);
        content=[tool('report','write',{path:'report.md',content:'Total: 10\n'})];
      }
      else if(turn===2)content=[record('record',details('plan').pending_action.id,'correct','Actual child total agrees with report','plan')];
      else if(turn===3){
        const action=details('record').pending_action;
        content=[tool('assess','agent_research_cycle',{operation:'assess',action_id:action.id,
          coverage:[{objective_id:action.objective_id,status:'met',refs:[ref('plan')],explanation:'Actual child observations agree'}],
          checks:action.checks.map(description=>({description,status:'passed',refs:[ref('plan')],explanation:'Actual source comparison'})),
          decision:'deliver',summary:'Actual saved report total agrees',follow_ups:[]})];
      }
      else if(turn===4){assert.equal(details('assess').status,'done');content=[{type:'text',text:'Automatic child result integrated.'}];}
      else throw Error('Automatic dispatch did not terminate');
    }else if(config.fixtureScenario==='delegated-work') {
      assert.match(context.systemPrompt,/empty writable directory does not mean/i);
      assert.match(context.systemPrompt,/inspected source paths/i);
      if(turn===0)content=[tool('plan','agent_research_cycle',plan)];
      else if(turn===1)content=[tool('delegate','agent_delegate',{tasks:[{id:'independent-total',title:'Independent CSV total',questions:objective.questions,expected_outputs:['Verified source total and child-result.md'],instruction:'Read the authorized read-only source '+config.fixtureSourcePath+', calculate its total, and save child-result.md in your output directory.'}]})];
      else if(turn===2){assert.equal(previous('delegate').details.children[0].status,'completed');assert.match(previous('delegate').details.children[0].answer,/10/);content=[tool('report','write',{path:'report.md',content:'Total: 10\n'})];}
      else if(turn===3)content=[record('record',details('plan').pending_action.id,'correct','Actual child source total agrees with report 10','delegate')];
      else if(turn===4)content=[assessment('assess',details('record').pending_action.id,'total','deliver','delegate')];
      else if(turn===5){assert.equal(details('assess').status,'done');content=[{type:'text',text:'Integrated actual child total 10 in report.md.'}];}
      else throw Error('Parent delegation did not terminate');
    }else if(['init-rejection','unplanned-work'].includes(config.fixtureScenario)) {
      if(turn===0)content=[config.fixtureScenario==='unplanned-work'?tool('bad-plan','write',{path:'report.md',content:'MUST NOT EXIST'}):tool('bad-plan','agent_research_cycle',{...plan,source_refs:['unadmitted']})];
      else if(turn===1){assert.equal(previous('bad-plan').isError,true);assert.equal(existsSync('report.md'),false,'unplanned write never executes');content=[{type:'text',text:'I stopped after a rejected plan.'}];}
      else if(turn===2){assert.ok(context.messages.some(m=>m.role==='user'&&JSON.stringify(m.content).includes('corrected plan')));content=[tool('plan','agent_research_cycle',plan)];}
      else if(turn===3)content=[tool('source-read','read',{path:'source.csv'})];
      else if(turn===4)content=[tool('write-report','write',{path:'report.md',content:'Total: 10\n'})];
      else if(turn===5)content=[record('record',details('plan').pending_action.id,'correct','Saved report total agrees with source 10','source-read')];
      else if(turn===6)content=[assessment('assess',details('record').pending_action.id,'total','deliver','source-read')];
      else if(turn===7){assert.equal(details('assess').status,'done');content=[{type:'text',text:'Report saved with verified total 10.'}];}
      else throw new Error('Rejected plan recovery did not terminate');
    }else if(turn===0)content=[tool('plan','agent_research_cycle',plan)];
    else if(turn===1)content=[tool('source-read','read',{path:'source.csv'})];
    else if(turn===2)content=[tool('wrong-report','write',{path:'report.md',content:'Total: 9\n'})];
    else if(turn===3)content=[record('record-wrong',details('plan').pending_action.id,'wrong','Saved report total 9 differs from source 10','source-read')];
    else if(turn===4)content=[assessment('revise',details('record-wrong').pending_action.id,'total','revise','source-read')];
    else if(turn===5){assert.equal(details('revise').phase,'executing');content=[{type:'text',text:'The actual report still needs repair.'}];}
    else if(turn===6){assert.ok(context.messages.some(m=>m.role==='user'&&JSON.stringify(m.content).includes('Repair the affected total')));
      const total=readFileSync('source.csv','utf8').trim().split('\n').slice(1).map(Number).reduce((a,b)=>a+b,0);
      content=[tool('correct-report','write',{path:'report.md',content:'Total: '+total+'\n'})];}
    else if(turn===7)content=[tool('verify-report','read',{path:'report.md'})];
    else if(turn===8)content=[record('record-correct',details('revise').pending_action.id,'correct','Actual saved report total agrees with source 10','verify-report')];
    else if(turn===9)content=[assessment('deliver',details('record-correct').pending_action.id,'repair','deliver','verify-report')];
    else if(turn===10){assert.equal(details('deliver').status,'done');assert.equal(readFileSync('report.md','utf8'),'Total: 10\n');content=[{type:'text',text:'The source total is 10 and corrected report.md is saved.'}];}
    else throw new Error('Research continuation did not terminate');
    if(!isChild)turn++;
    const message={role:'assistant',content,api:model.api,provider:model.provider,model:model.id,timestamp:Date.now(),
      usage:{input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}},
      stopReason:content.some(item=>item.type==='toolCall')?'toolUse':'stop'};
    if(isReviewChild&&config.fixtureScenario==='limited-delivery')Object.assign(message,{content:[],stopReason:'error',errorMessage:'Offline review transport failure'});
    const stream=ai.createAssistantMessageEventStream();stream.push({type:'done',reason:message.stopReason,message});stream.end();return stream;
  }};
const fixtureSdk={...sdk,DefaultResourceLoader:class extends sdk.DefaultResourceLoader {
  async reload(){await super.reload();
    const failures=this.getExtensions().errors;
    if(failures.length)throw new Error('Offline resource setup: '+JSON.stringify(failures));
  }
}};
await runManagedSession(config,fixtureSdk,modelRuntime);
if(recoveryScenario){
  const {configureGeneralResearch}=await import(new URL('./general-research.mjs',process.argv[3]));
  const tools=new Map();configureGeneralResearch({on(){},registerTool:tool=>tools.set(tool.name,tool)},config);
  const overview=await tools.get('agent_research_read').execute('legacy-overview',{section:'overview'});
  assert.equal(overview.details.ok,true);assert.ok(!Object.hasOwn(overview.details.result,'cycle'),'legacy caller without controller callback keeps its ledger-only contract');
  assert.ok(!JSON.stringify(overview.details.result.notes).includes('runtime.checkpoint.'));
}
assert.equal(turn,automaticScenario?5:discoveryDriven?13:recoveryScenario||['review-version-recovery','producer-checkpoint'].includes(config.fixtureScenario)?13:config.fixtureScenario==='split-only'?11:config.fixtureScenario==='direct-chat'?1:['init-rejection','unplanned-work','limited-delivery'].includes(config.fixtureScenario)?8:['delegated-work','limited-checker'].includes(config.fixtureScenario)?6:config.fixtureScenario==='mcp-work'?7:11);
if(automaticScenario)assert.equal(childTurns,config.fixtureScenario==='automatic-ready-work'?6:3);
if(config.fixtureScenario==='delegated-work')assert.equal(childTurns,3);
if(discoveryDriven){assert.equal(childTurns,6);assert.equal(childTurnsByDirectory.size,2);assert.ok([...childTurnsByDirectory.values()].every(count=>count===3));}
