import test from 'node:test';
import assert from 'node:assert/strict';
import {checkGatewayToolUse,gatewayToolGroup,createGatewayUseLedger} from '../../src/capstone_agent/resources/gateway-tool-use.mjs';

test('toolset labels do not define client permission or fallback policy',()=>{
 for(const group of ['readonly_sql','arbitrary_relation','operation']){
  const publication={_meta:{'data-gateway/toolset':group}};
  assert.equal(gatewayToolGroup(publication),group);
  assert.deepEqual(checkGatewayToolUse(['renamed_tool'],{tools:{renamed_tool:publication}}),{allowed:true});
 }
});

test('observation ledger retains exact issued references without granting tools',()=>{
 const ledger=createGatewayUseLedger();
 ledger.record('renamed_tool','observation:issued');
 assert.equal(ledger.has('renamed_tool','observation:issued'),true);
 assert.equal(ledger.has('other','observation:issued'),false);
 assert.equal(ledger.has('renamed_tool','observation:invented'),false);
});
