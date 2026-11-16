const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const template=fs.readFileSync(path.join(__dirname,'template.html'),'utf8');
const fallback={schema:'capstone-project-overview/1',generated_at:100,updated:'snapshot',main:'a'.repeat(40)};
for(const key of ['nodes','edges','packages','environments','proposals','package_details','discussion',
  'environment_pairs','development_lines','branches','prs','hotfix_branches','uncommitted'])fallback[key]=[];
function select(live){
  const script=template.match(/<script id="project-bootstrap">([\s\S]*?)<\/script>/);
  assert.ok(script,'snapshot selection bootstrap must be present');
  const window={CAPSTONE_PROJECT_OVERVIEW_LIVE:live};
  const document={getElementById:()=>({textContent:JSON.stringify(fallback)})};
  vm.runInNewContext(script[1],{window,document,Date:{now:()=>1_000_000}});
  return JSON.parse(JSON.stringify(window.CAPSTONE_PROJECT_OVERVIEW));
}
test('missing live file uses the embedded offline snapshot',()=>{
  assert.deepEqual(select(undefined),{data:fallback,mode:'snapshot'});
});
test('fresh valid live state replaces the embedded snapshot',()=>{
  const live={...fallback,generated_at:200,updated:'live'};
  assert.deepEqual(select(live),{data:live,mode:'live'});
});
test('stale, future, wrong-schema and malformed live state cannot replace the snapshot',()=>{
  for(const live of [{...fallback,generated_at:99},{...fallback,generated_at:1001},{...fallback,generated_at:2000},
    {...fallback,schema:'other'}, {...fallback,nodes:null},
    {schema:fallback.schema,generated_at:200,nodes:[],edges:[]},null,{},'invalid']){
    assert.deepEqual(select(live),{data:fallback,mode:'snapshot'});
  }
});
