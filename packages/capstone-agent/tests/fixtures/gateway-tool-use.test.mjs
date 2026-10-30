import test from 'node:test';
import assert from 'node:assert/strict';
import {checkGatewayToolUse,gatewayToolGroup,createGatewayUseLedger} from '../../src/capstone_agent/resources/gateway-tool-use.mjs';

const business={_meta:{'data-gateway/toolset':'operation'}};
const advanced={_meta:{'data-gateway/toolset':'readonly_sql'}};
const catalog={tools:{renamed_statistics:business,renamed_exploration:advanced}};

test('selection follows published toolset membership, never tool spelling',()=>{
 assert.equal(gatewayToolGroup(advanced),'readonly_sql');
 assert.equal(checkGatewayToolUse(['renamed_statistics'],catalog).allowed,true);
 assert.equal(checkGatewayToolUse(['renamed_exploration'],catalog).allowed,false);
 assert.equal(checkGatewayToolUse(['execute_readonly_sql'],{tools:{execute_readonly_sql:business}}).allowed,true);
});

test('advanced exploration needs a bounded declared capability gap, not a new approval loop',()=>{
 const allowed=checkGatewayToolUse(['renamed_exploration'],catalog,{reason:'capability_gap',detail:'The requested cross-source relation has no published operation.'});
 assert.equal(allowed.allowed,true);assert.match(allowed.declaration.detail,/cross-source/);
 assert.deepEqual(allowed.declaration.tools,['renamed_exploration']);
 for(const reason of [undefined,' ',42,'x'.repeat(1001)])assert.equal(checkGatewayToolUse(['renamed_exploration'],catalog,reason).allowed,false);
});

test('a recorded suspected defect can use exploration without being certified as a confirmed gateway bug',()=>{
 const why={reason:'tool_defect',detail:'The documented valid request returned inconsistent object references.',tool_issue:{tool:'renamed_statistics',observation_ref:'observation:actual-call'}};
 const ledger=createGatewayUseLedger();
 assert.equal(checkGatewayToolUse(['renamed_exploration'],catalog,why,ledger).allowed,false);
 ledger.record('renamed_statistics','observation:actual-call');
 const result=checkGatewayToolUse(['renamed_exploration'],catalog,why,ledger);
 assert.equal(result.allowed,true);assert.equal(result.declaration.basis,'agent_reported_suspected_defect');
 assert.deepEqual(result.declaration.tool_issue,why.tool_issue);
 for(const issue of [undefined,{tool:'unknown',observation_ref:'o1'},{tool:'renamed_statistics'}, {tool:'renamed_exploration',observation_ref:'o1'}]){
  assert.equal(checkGatewayToolUse(['renamed_exploration'],catalog,{...why,tool_issue:issue},ledger).allowed,false);
 }
 assert.equal(checkGatewayToolUse(['renamed_exploration'],catalog,{...why,tool_issue:{...why.tool_issue,observation_ref:'never-issued'}},ledger).allowed,false);
});
