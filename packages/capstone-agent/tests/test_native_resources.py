import json
from pathlib import Path
import subprocess

import pytest

from capstone_agent.runtime_resources import ResolvedResourceProfile, ResourceDescriptor


def profile():
    resource = ResourceDescriptor('sample', 'skill', 'v1', 'local', ('direct_pi',), True,
                                  True, True, None, (), 'identity')
    return ResolvedResourceProfile('project', 'revision', 'direct_pi', (), (resource,), (), None, None,
                                  json.dumps({'resources': [{'id': 'sample', 'native_name': 'sample'}]}))


def test_typed_input_requires_exact_ready_skill_version():
    from capstone_agent.native_resources import validate_native_input
    assert validate_native_input({'kind': 'text', 'text': '/skill:sample literal'}, profile()) is None
    assert validate_native_input({'kind': 'skill_invocation', 'text': 'args',
                                 'skill_id': 'sample', 'skill_version': 'v1'}, profile()) == 'sample'
    for version in ['v2', '']:
        with pytest.raises(ValueError):
            validate_native_input({'kind': 'skill_invocation', 'text': 'args',
                                   'skill_id': 'sample', 'skill_version': version}, profile())


def test_mcp_schema_is_hashed_before_validation_and_never_fetches():
    from capstone_agent.bounded_mcp import validate_arguments
    from capstone_agent.runtime_resources import content_hash
    schema = {'name': 'fixed', 'inputSchema': {'type': 'object', '$ref': 'https://invalid.example/schema'}}
    with pytest.raises(ValueError, match='identity'):
        validate_arguments('fixed', {}, {'fixed': schema}, {'fixed': 'changed'})
    with pytest.raises(ValueError, match='schema'):
        validate_arguments('fixed', {}, {'fixed': schema}, {'fixed': content_hash(schema)})
    schema = {'name': 'fixed', 'inputSchema': {'type': 'object', 'properties': {'a': {'type': 'integer'}},
                                             'required': ['a'], 'additionalProperties': False}}
    hashes = {'fixed': content_hash(schema)}
    validate_arguments('fixed', {'a': 1}, {'fixed': schema}, hashes)
    with pytest.raises(ValueError):
        validate_arguments('fixed', {'a': 'wrong'}, {'fixed': schema}, hashes)
    with pytest.raises(ValueError):
        validate_arguments('endpoint', {}, {'fixed': schema}, hashes)


def test_sdk_entry_disables_expansion_for_text_and_checks_skill_collision(tmp_path):
    entry = Path(__file__).parents[1] / 'src/capstone_agent/resources/general-sdk.mjs'
    assert entry.is_file(), 'managed SDK entry is required'
    script = '''import { promptInput } from process.env.ENTRY;
const calls=[]; const session={prompt:async(...args)=>calls.push(args),
resourceLoader:{getSkills:()=>({skills:[{name:"sample"}]}),getPromptTemplates:()=>[]},
extensionRunner:{getCommand:()=>undefined}};
await promptInput(session,{kind:"text",text:"/skill:sample literal"},null);
await promptInput(session,{kind:"skill_invocation",text:"args"},"sample");
session.extensionRunner.getCommand=()=>({});
let blocked=false;try {await promptInput(session,{kind:"skill_invocation",text:"args"},"sample")}catch {blocked=true}
console.log(JSON.stringify({calls,blocked}));'''
    # Dynamic imports permit the test to use the exact managed helper without a model.
    script = script.replace('import { promptInput } from process.env.ENTRY;',
                            'const {promptInput}=await import(process.env.ENTRY);')
    result = subprocess.run([__import__('shutil').which('node'), '--input-type=module', '-e', script],
                            env={'ENTRY': entry.as_uri()}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'calls': [['/skill:sample literal', {'expandPromptTemplates': False}],
                                                  ['/skill:sample args', {'expandPromptTemplates': True}]], 'blocked': True}


def test_store_retains_old_native_settings_and_role_identity(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    root = config(tmp_path)
    store = NativeResourceStore(root, tmp_path / 'profiles')
    first = store.profiles['direct_pi']
    state = store.accepted('direct_pi', first.revision)
    skill = root / 'native/skill/SKILL.md'
    skill.write_text(skill.read_text() + 'Changed current input.\n')
    next_store = NativeResourceStore(root, tmp_path / 'profiles')
    assert next_store.profiles['direct_pi'].revision != first.revision
    assert 'Changed current' not in (Path(state['settings'][0]).parent / 'skills-0/SKILL.md').read_text()
    with pytest.raises(ValueError, match='role'):
        next_store.accepted('delegated_pi', first.revision)
    assert str(tmp_path) not in json.dumps(first.to_document())


def test_actual_publication_required_for_ready_profiles(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    root = config(tmp_path)
    store = NativeResourceStore(root, tmp_path / 'profiles')
    before = store.profiles['direct_pi']
    assert not before.resources[0].ready
    with pytest.raises(ValueError, match='publication'):
        store.confirm_loaded('direct_pi', {'tools': ['read'], 'skills': []})
    confirmed = store.confirm_loaded('direct_pi', {'tools': ['read'], 'skills': [{'name': 'sample',
        'sha256': __import__('hashlib').sha256((root / 'native/skill/SKILL.md').read_bytes()).hexdigest()}]})
    assert confirmed.resources[0].ready
    assert confirmed.revision != before.revision
    assert store.accepted('direct_pi', confirmed.revision)['load_receipt']['status'] == 'passed'


def test_revoked_resource_and_frozen_snapshot_drift_fail(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    root = config(tmp_path)
    store = NativeResourceStore(root, tmp_path / 'profiles')
    profile_ = store.profiles['direct_pi']
    manifest_path = root / 'agent-resources.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['resources'][0]['enabled'] = False
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='revoked'):
        store.accepted('direct_pi', profile_.revision)


def test_ready_profile_uses_the_snapshot_that_was_actually_probed(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    import hashlib
    root = config(tmp_path)
    store = NativeResourceStore(root, tmp_path / 'profiles')
    original = (root / 'native/skill/SKILL.md').read_bytes()
    (root / 'native/skill/SKILL.md').write_text('changed after probe')
    ready = store.confirm_loaded('direct_pi', {'tools': ['read'], 'skills': [
        {'name': 'sample', 'sha256': hashlib.sha256(original).hexdigest()}]})
    state = store.accepted('direct_pi', ready.revision)
    assert (Path(state['settings'][0]).parent / 'skills-0/SKILL.md').read_bytes() == original


def test_bounded_bridge_abort_stops_connection_without_retry():
    entry = Path(__file__).parents[1] / 'src/capstone_agent/resources/general-mcp.mjs'
    script = '''const {BoundedMcp} = await import(process.env.ENTRY);
const bridge=new BoundedMcp({deadlineAt:Date.now()+10000});
let killed=0; bridge.child={kill:()=>{killed++}};
const control=new AbortController();
const pending=bridge.wait(control.signal,10000); control.abort();
let message='';try {await pending}catch(error){message=error.message}
let repeat=false; try {await bridge.wait(null,10000)}catch{repeat=true}
console.log(JSON.stringify({killed,closed:bridge.closed,message,repeat}));'''
    result = subprocess.run([__import__('shutil').which('node'), '--input-type=module', '-e', script],
                            env={'ENTRY': entry.as_uri()}, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'killed': 1, 'closed': True,
        'message': 'MCP outcome unknown; do not retry', 'repeat': True}


def test_native_mcp_receipt_checks_actual_schema_and_extension_owner():
    entry = Path(__file__).parents[1] / 'src/capstone_agent/resources/general-sdk.mjs'
    script = '''const {verifyMcpPublication} = await import(process.env.ENTRY);
const schema={name:"fixed",description:"Fixed tool",inputSchema:{type:"object"}};
const tool={name:"fixed",description:"Fixed tool",parameters:{type:"object"}};
const config={mcp:{descriptor:{tool_schemas:{fixed:schema},tool_schema_hashes:{fixed:"accepted"}}},extensions:["/managed/mcp.mjs"]};
const extension={resolvedPath:"/managed/mcp.mjs",tools:new Map([["fixed",{}]])};
const session={getAllTools:()=>[tool],resourceLoader:{getExtensions:()=>({extensions:[extension]})}};
let good=verifyMcpPublication(session,config), schemaBlocked=false, ownerBlocked=false;
tool.parameters={type:"string"};try{verifyMcpPublication(session,config)}catch{schemaBlocked=true}
tool.parameters={type:"object"};extension.resolvedPath="/unaccepted/tool.mjs";
try{verifyMcpPublication(session,config)}catch{ownerBlocked=true}
console.log(JSON.stringify({good,schemaBlocked,ownerBlocked}));'''
    result = subprocess.run([__import__('shutil').which('node'), '--input-type=module', '-e', script],
                            env={'ENTRY': entry.as_uri()}, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'good': {'fixed': 'accepted'}, 'schemaBlocked': True, 'ownerBlocked': True}


def test_unavailable_skill_is_not_loaded_for_ordinary_task(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    from types import SimpleNamespace
    root = config(tmp_path)
    path = root / 'agent-resources.json'
    declaration = json.loads(path.read_text())
    declaration['resources'][0]['required_tools'] = ['missing']
    path.write_text(json.dumps(declaration))
    store = NativeResourceStore(root, tmp_path / 'profiles')
    confirmed = store.confirm_loaded('direct_pi', {'tools': ['read'], 'skills': [{'name': 'sample',
        'sha256': __import__('hashlib').sha256((root / 'native/skill/SKILL.md').read_bytes()).hexdigest()}]})
    assert not confirmed.resources[0].ready
    request = SimpleNamespace(instruction='Explain', task_id='task', parent_attempt_id='attempt',
                              to_document=lambda: {})
    assert store.task_config('direct_pi', confirmed.revision, workspace=tmp_path / 'task', request=request)['allowedSkills'] == []


def test_full_native_config_and_policy_are_frozen_for_retry(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    from types import SimpleNamespace
    root = config(tmp_path)
    native = root / 'native'
    for name in ('AGENTS.md', 'SYSTEM.md', 'APPEND_SYSTEM.md'):
        (native / name).write_text('Accepted ' + name)
    (native / 'prompts').mkdir()
    (native / 'prompts/example.md').write_text('Accepted prompt')
    settings = json.loads((native / 'settings.json').read_text())
    settings['defaultTools'] = ['read', 'bash']
    (native / 'settings.json').write_text(json.dumps(settings))
    first = NativeResourceStore(root, tmp_path / 'profiles')
    accepted = first.profiles['direct_pi']
    for name in ('AGENTS.md', 'SYSTEM.md', 'APPEND_SYSTEM.md'):
        (native / name).write_text('Changed ' + name)
    second = NativeResourceStore(root, tmp_path / 'profiles')
    assert second.profiles['direct_pi'].revision != accepted.revision
    request = SimpleNamespace(instruction='Explain', task_id='task', parent_attempt_id='attempt',
                              to_document=lambda: {})
    values = second.task_config('direct_pi', accepted.revision, workspace=tmp_path / 'task', request=request)
    assert values['settings']['defaultTools'] == ['read', 'bash']
    assert values['systemPrompt'] == 'Accepted SYSTEM.md'
    assert values['appendSystemPrompt'] == ['Accepted APPEND_SYSTEM.md']
    assert values['contextFiles'][0]['content'] == 'Accepted AGENTS.md'
    assert Path(values['settings']['prompts'][0], 'example.md').read_text() == 'Accepted prompt'


@pytest.mark.parametrize('key,filename', [('prompts', 'example.md'), ('themes', 'example.json')])
def test_external_native_resource_bytes_change_new_revision_only(tmp_path, key, filename):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    root = config(tmp_path)
    shared = root / ('shared-' + key)
    shared.mkdir()
    (shared / filename).write_text('version one')
    settings = json.loads((root / 'native/settings.json').read_text())
    settings[key] = ['../' + shared.name]
    (root / 'native/settings.json').write_text(json.dumps(settings))
    first = NativeResourceStore(root, tmp_path / 'profiles')
    old = first.profiles['direct_pi']
    state = first.accepted('direct_pi', old.revision)
    retained = Path(state['settings'][0]).parent / (key + '-0') / filename
    (shared / filename).write_text('version two')
    second = NativeResourceStore(root, tmp_path / 'profiles')
    current = second.profiles['direct_pi']
    assert current.revision != old.revision
    new_state = second.accepted('direct_pi', current.revision)
    assert (Path(new_state['settings'][0]).parent / (key + '-0') / filename).read_text() == 'version two'
    assert retained.read_text() == 'version one'
    assert second.accepted('direct_pi', old.revision)['profile']['revision'] == old.revision


def test_extension_sibling_bytes_and_original_layout_are_retained(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    root = config(tmp_path)
    package = root / 'extension-package'
    package.mkdir()
    (package / 'extension.mjs').write_text('import {value} from "./helper.mjs"; export default function(){}')
    (package / 'helper.mjs').write_text('export const value="old";')
    settings = json.loads((root / 'native/settings.json').read_text())
    settings['extensions'] = ['../extension-package/extension.mjs']
    (root / 'native/settings.json').write_text(json.dumps(settings))
    store = NativeResourceStore(root, tmp_path / 'profiles')
    old = store.profiles['direct_pi']
    state = store.accepted('direct_pi', old.revision)
    frozen_settings = Path(state['settings'][0])
    extension = frozen_settings.parent / json.loads(frozen_settings.read_text())['extensions'][0]
    assert extension.name == 'extension.mjs'
    assert (extension.parent / 'helper.mjs').read_text() == 'export const value="old";'
    (package / 'helper.mjs').write_text('export const value="new";')
    second = NativeResourceStore(root, tmp_path / 'profiles')
    assert second.profiles['direct_pi'].revision != old.revision
    assert (extension.parent / 'helper.mjs').read_text() == 'export const value="old";'


@pytest.mark.parametrize('unsafe', ['parent-import', 'auth'])
def test_native_resource_declared_root_rejects_escape_and_auth(tmp_path, unsafe):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    root = config(tmp_path)
    package = root / 'native/extensions'
    package.mkdir()
    (package / 'extension.mjs').write_text('import "../outside.mjs"; export default function(){}'
                                         if unsafe == 'parent-import' else 'export default function(){}')
    (root / 'native/outside.mjs').write_text('export const value=1;')
    if unsafe == 'auth':
        (package / 'auth.json').write_text('{"fixture":"no-secret"}')
    settings = json.loads((root / 'native/settings.json').read_text())
    settings['extensions'] = ['extensions/extension.mjs']
    (root / 'native/settings.json').write_text(json.dumps(settings))
    with pytest.raises(ValueError, match='declared root|protected transport'):
        NativeResourceStore(root, tmp_path / 'profiles')


def test_interrupted_snapshot_restarts_and_preserves_valid_old_snapshot(tmp_path, monkeypatch):
    from test_runtime_resources import config
    import capstone_agent.native_resources as module
    root = config(tmp_path)
    snapshots = tmp_path / 'profiles'
    first = module.NativeResourceStore(root, snapshots)
    old = first.profiles['direct_pi']
    before = {str(path.relative_to(snapshots / old.revision)): path.read_bytes()
              for path in (snapshots / old.revision).rglob('*') if path.is_file()}
    skill = root / 'native/skill/SKILL.md'
    skill.write_text(skill.read_text() + 'New resource version.\n')
    copy = module.shutil.copytree
    def interrupt(source, destination, *args, **kwargs):
        copy(source, destination, *args, **kwargs)
        raise OSError('fixture mid-copy interruption')
    monkeypatch.setattr(module.shutil, 'copytree', interrupt)
    with pytest.raises(OSError, match='mid-copy'):
        module.NativeResourceStore(root, snapshots)
    monkeypatch.setattr(module.shutil, 'copytree', copy)
    restored = module.NativeResourceStore(root, snapshots)
    current = restored.profiles['direct_pi']
    assert current.revision != old.revision
    assert restored.accepted('direct_pi', current.revision)['profile']['revision'] == current.revision
    after = {str(path.relative_to(snapshots / old.revision)): path.read_bytes()
             for path in (snapshots / old.revision).rglob('*') if path.is_file()}
    assert after == before
    assert not list(snapshots.glob('.pending-*'))


def test_existing_unpublished_final_snapshot_is_recovered(tmp_path):
    from test_runtime_resources import config
    from capstone_agent.native_resources import NativeResourceStore
    import shutil
    root = config(tmp_path)
    snapshots = tmp_path / 'profiles'
    first = NativeResourceStore(root, snapshots)
    profile_ = first.profiles['direct_pi']
    destination = snapshots / profile_.revision
    for path in [destination, *destination.rglob('*')]:
        path.chmod(0o700 if path.is_dir() else 0o600)
    shutil.rmtree(destination)
    destination.mkdir()
    (destination / 'partial-copy').write_text('unpublished fixture')
    restarted = NativeResourceStore(root, snapshots)
    assert restarted.accepted('direct_pi', profile_.revision)['profile']['revision'] == profile_.revision
    assert not (destination / 'partial-copy').exists()
