import test from 'node:test';
import assert from 'node:assert/strict';
import {createToolDiscovery} from '../../src/capstone_agent/resources/general-tool-discovery.mjs';
import {createDataGatewayTools} from '../../src/capstone_agent/resources/general-data-gateway.mjs';

test('search and execution preserve complete provider conditions within the existing summary budget',async()=>{
 const semantics={execution_choice:'Use only a current snapshot.',prerequisites:['An issued reference is required.'],
  applicable_questions:['Read selected fields'],composition_constraints:['x'.repeat(2000)]};
 const publications={opaque:{name:'published_read',description:'Read bounded fields',
  _meta:{'data-gateway/capability':{summary_version:'capability-summary/1',declaration_basis:'provider_declared',
   id:'x'.repeat(2000),semantics}}}};
 const original=structuredClone(publications);
 const config={dataGateway:{catalog:{tools:publications}}};
 const tools=createDataGatewayTools(config);
 const c=createToolDiscovery({tools,publications,admittedNames:['opaque'],maxSummaryChars:512});
 const result=JSON.parse((await c.tools[0].execute('find',{query:'published_read'})).content[0].text);
 const selection=result.tools[0].published_selection;
 assert.deepEqual(selection.fields.execution_choice,semantics.execution_choice);
 assert.deepEqual(selection.fields.prerequisites,semantics.prerequisites);
 assert.ok(selection.omitted_fields.includes('composition_constraints'));
 assert.ok(JSON.stringify(selection).length<=512);
 assert.equal(selection.fields.composition_constraints,undefined);
 assert.ok(tools[0].description.includes(semantics.prerequisites[0]));
 assert.ok(!tools[0].description.includes('x'.repeat(100)));
 assert.deepEqual(publications,original);
});

test('unknown declaration versions keep generic metadata and never assert selection semantics',async()=>{
 const publications={opaque:{name:'published_read',description:'Read',_meta:{'data-gateway/capability':{
  summary_version:'capability-summary/99',declaration_basis:'provider_declared',semantics:{prerequisites:['unknown contract']}}}}};
 const tools=createDataGatewayTools({dataGateway:{catalog:{tools:publications}}});
 const c=createToolDiscovery({tools,publications,admittedNames:['opaque'],maxSummaryChars:80});
 const result=JSON.parse((await c.tools[0].execute('find',{query:'published_read'})).content[0].text);
 assert.equal(result.tools[0].published_selection,undefined);
 assert.ok(result.tools[0].published_metadata_preview.length<=80);
 assert.equal(tools[0].description,'Read');
});

test('direct model descriptions respect the task summary capacity snapshot',()=>{
 const publication={description:'Read',_meta:{'data-gateway/capability':{summary_version:'capability-summary/1',
  declaration_basis:'provider_declared',semantics:{execution_choice:'x'.repeat(200)}}}};
 const [tool]=createDataGatewayTools({runtimeLimits:{tool_summary_chars:80},dataGateway:{catalog:{tools:{opaque:publication}}}});
 assert.ok(!tool.description.includes('x'.repeat(100)));
 const summary=JSON.parse(tool.description.slice(tool.description.indexOf('{')));
 assert.ok(JSON.stringify(summary).length<=80);
});
