import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createSkillRecordTool,admitSkillPresentation,skillSelectionGuidance} from '../../src/capstone_agent/resources/investigation-skills.mjs';
import {applicationToolOptions} from '../../src/capstone_agent/resources/general-sdk.mjs';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

test('skill records require an admitted load and distinguish reported use from verification',async()=>{
  const root=await mkdtemp(join(tmpdir(),'skills-'));
  try{
    const path=join(root,'SKILL.md');await writeFile(path,'# Method\nUse evidence.');
    const tool=createSkillRecordTool([{name:'method',description:'Investigate',filePath:path}]);
    assert.equal((await tool.execute('before',{name:'method',operation:'report',summary:'Testing'})).isError,true);
    assert.equal((await tool.execute('unknown',{name:'other',operation:'load'})).isError,true);
    const loaded=await tool.execute('load',{name:'method',operation:'load'});
    assert.equal(loaded.details.skill_activity.state,'loaded');
    assert.equal(loaded.details.skill_activity.source,'host');
    assert.equal((await tool.execute('empty-phase',{name:'method',operation:'report',summary:'Checked',phase:''})).isError,true);
    const report=await tool.execute('apply',{name:'method',operation:'report',summary:'Checked coverage',phase:'quality',refs:['result:one'],tool_call_ids:['read-1']});
    assert.equal(report.details.skill_activity.state,'reported');
    assert.equal(report.details.skill_activity.source,'model');
    assert.deepEqual(report.details.skill_activity.refs,['result:one']);
    assert.equal(report.details.skill_activity.verified,undefined);
    await writeFile(path,'Changed method');
    assert.equal((await tool.execute('changed',{name:'method',operation:'report',summary:'done'})).isError,true);
  }finally{await rm(root,{recursive:true,force:true});}
});

test('pinned SDK uses the admitted semantic catalog instead of host-file instructions',async()=>{
  const sdk=await import(pathToFileURL(resolve('.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
  const config={allowedSkills:['data-investigation'],applicationPolicy:{allowed_tools:['agent_skill']}};
  const loader=new sdk.DefaultResourceLoader({cwd:process.cwd(),agentDir:resolve('.grid-agent/skill-test-empty'),
    settingsManager:sdk.SettingsManager.inMemory({}),noSkills:true,noExtensions:true,noContextFiles:true,
    noPromptTemplates:true,noThemes:true,additionalSkillPaths:[resolve('configs/runtime/general-pi/skills')],
    skillsOverride:current=>admitSkillPresentation(config,current),
    appendSystemPromptOverride:()=>[skillSelectionGuidance(config)]});
  await loader.reload();
  assert.deepEqual(config.taskSkills.map(s=>s.name),['data-investigation']);
  assert.equal(sdk.formatSkillsForPrompt(loader.getSkills().skills),'');
  const guidance=loader.getAppendSystemPrompt().join('\n');
  assert.ok(guidance.includes('data-investigation'));
  assert.ok(guidance.includes('agent_skill'));
  assert.ok(!guidance.includes('SKILL.md')&&!guidance.includes(process.cwd()));
  assert.ok(!guidance.includes('systematic-debugging'));
  const tool=applicationToolOptions(config,[]).customTools.find(t=>t.name==='agent_skill');
  assert.equal((await tool.execute('load',{name:'data-investigation',operation:'load'})).details.skill_activity.state,'loaded');
});

test('does not advertise the semantic skill loader without its tool grant',()=>{
  const config={allowedSkills:['method'],applicationPolicy:{allowed_tools:['read']}};
  const source={skills:[{name:'method',description:'A method',filePath:'/private/method'}],diagnostics:[]};
  assert.deepEqual(admitSkillPresentation(config,source),source);
  assert.equal(skillSelectionGuidance(config),'');
});

test('pinned SDK discovers the six native methods and publishes their admitted record tool',async()=>{
  const sdk=await import(pathToFileURL(resolve('.grid-agent/runtime/pi/source/packages/coding-agent/dist/index.js')).href);
  const loader=new sdk.DefaultResourceLoader({cwd:process.cwd(),agentDir:resolve('.grid-agent/skill-test-empty'),
    settingsManager:sdk.SettingsManager.inMemory({}),noSkills:true,noExtensions:true,noContextFiles:true,
    noPromptTemplates:true,noThemes:true,additionalSkillPaths:[resolve('configs/runtime/general-pi/skills')]});
  await loader.reload();
  const skills=loader.getSkills().skills;
  assert.equal(skills.length,6);
  assert.ok(skills.every(skill=>skill.filePath.endsWith('/SKILL.md')));
  const config={allowedSkills:skills.map(s=>s.name),taskSkills:skills,applicationPolicy:{allowed_tools:['agent_skill']}};
  const tools=applicationToolOptions(config,[]).customTools;
  const tool=tools.find(t=>t.name==='agent_skill');
  assert.ok(tool);
  const result=await tool.execute('load',{name:'data-investigation',operation:'load'});
  assert.equal(result.details.skill_activity.state,'loaded');
  assert.ok(result.content[0].text.includes('held-out'));
});
