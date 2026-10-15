"""Local OpenAI-compatible configuration; never send a Provider request."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from capstone_agent.runtime import resolve_harness_llm
from capability_agent.runtime.environment import RuntimePaths, build_pi_launch
from capability_agent.runtime.locator import PiRuntimeLocator
from capability_agent.runtime.lock import PiRuntimeLock

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('offline_host_runtime', ROOT / 'deploy/launch_host_runtime.py')
assert SPEC and SPEC.loader
RUNTIME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNTIME)


def environment(application):
    return {'CAPSTONE_RUNTIME_PROFILE': 'capstone-dev-trial-v1',
            'CAPSTONE_DEPLOYMENT_STAGE': 'local', 'CAPSTONE_HOSTED_APPLICATION': application,
            'PROVIDER': 'openai', 'CAPSTONE_PUBLIC_PROVIDER': 'deepseek',
            'CAPSTONE_PUBLIC_MODEL': 'old-model', 'OPENAI_MODEL': 'deepseek-flash',
            'OPENAI_BASE_URL': 'https://llm.example.internal/v1',
            'OPENAI_API_KEY': 'test-only-key'}


@pytest.mark.parametrize('application', ['pandapower', 'pypsa'])
def test_aliases_reach_actual_worker_resolution(application):
    selected = RUNTIME.select_runtime(ROOT, environment(application), 'worker')[3]
    resolved = resolve_harness_llm(ROOT, selected)
    assert resolved.config.provider == 'openai'
    assert resolved.config.model == 'deepseek-flash'
    assert resolved.config.base_url == 'https://llm.example.internal/v1'
    assert resolved.config.compatibility_profile == 'openai-completions'


@pytest.mark.parametrize('profile,endpoint,expected', [
    ('capstone-dev-trial-v1', 'https://api.openai.com/v1', 'openai-responses'),
    ('capstone-dev-trial-v1', 'https://api.openai.com/v1/', 'openai-responses'),
    ('capstone-workbench-v1', 'https://llm.example.internal/v1', 'openai-responses'),
])
def test_openai_protocol_selection_stays_within_local_custom_endpoints(profile, endpoint, expected):
    settings = {'CAPSTONE_RUNTIME_PROFILE': profile, 'CAPSTONE_PUBLIC_PROVIDER': 'openai',
                'CAPSTONE_PUBLIC_MODEL': 'deepseek-flash', 'OPENAI_API_KEY': 'test-only-key',
                'CAPABILITY_AGENT_LLM_BASE_URL': endpoint}
    resolved = resolve_harness_llm(ROOT, settings)
    assert resolved.config.compatibility_profile == expected


def test_aliases_do_not_change_fixed_cloud_profile():
    settings = environment('pandapower')
    settings.update(CAPSTONE_RUNTIME_PROFILE='capstone-workbench-v1',
                    CAPSTONE_PUBLIC_MODEL='deepseek-flash', DEEPSEEK_API_KEY='test-only-key')
    selected = RUNTIME.select_runtime(ROOT, settings, 'worker')[3]
    resolved = resolve_harness_llm(ROOT, selected)
    assert resolved.config.provider == 'deepseek'
    assert resolved.config.base_url == 'https://api.deepseek.com'


@pytest.mark.parametrize('provider,model', [('deepseek', 'deepseek-flash'), ('openai', 'gpt-5.5')])
def test_existing_explicit_settings_work_with_empty_aliases(provider, model):
    settings = environment('pandapower')
    settings.update(PROVIDER='', OPENAI_MODEL='', OPENAI_BASE_URL='',
                    CAPSTONE_PUBLIC_PROVIDER=provider, CAPSTONE_PUBLIC_MODEL=model,
                    DEEPSEEK_API_KEY='test-only-key')
    selected = RUNTIME.select_runtime(ROOT, settings, 'worker')[3]
    resolved = resolve_harness_llm(ROOT, selected)
    assert resolved.config.provider == provider
    assert resolved.config.model == model
    assert 'CAPABILITY_AGENT_LLM_BASE_URL' not in selected


@pytest.mark.skipif(not shutil.which('docker'), reason='Docker CLI is required for real Compose interpolation')
def test_compose_aliases_and_worker_only_endpoint():
    settings = {key: value for key, value in os.environ.items()
                if not key.startswith(('CAPSTONE_', 'OPENAI_', 'DEEPSEEK_')) and key != 'PROVIDER'}
    settings.update(environment('pandapower'))
    settings.update(POSTGRES_PASSWORD='test-password', CAPSTONE_OPERATOR_TOKEN='test-token',
                    S3_ACCESS_KEY='test-access', S3_SECRET_KEY='test-secret')
    settings.update({f'CAPSTONE_{name}_IMAGE': f'test-{name.lower()}:offline'
                     for name in ['BACKEND', 'APP', 'POSTGRES', 'OBJECTS']})
    result = subprocess.run(['docker', 'compose', '--env-file', '/dev/null', '-f',
                             str(ROOT / 'deploy/dev-trial/compose.yaml'), '--profile', 'tools',
                             'config', '--format', 'json'], env=settings, capture_output=True, text=True)
    assert result.returncode == 0, 'Compose configuration failed'
    services = json.loads(result.stdout)['services']
    for name in ['worker', 'worker-pypsa', 'config-check']:
        selected = services[name]['environment']
        assert selected['PROVIDER'] == 'openai'
        assert selected['OPENAI_MODEL'] == 'deepseek-flash'
        assert selected['OPENAI_BASE_URL'] == 'https://llm.example.internal/v1'
        assert selected['OPENAI_API_KEY'] == 'test-only-key'
    for name in ['api', 'app']:
        assert not {'OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'OPENAI_BASE_URL'} & services[name]['environment'].keys()


@pytest.mark.parametrize('application', ['pandapower', 'pypsa'])
@pytest.mark.parametrize('endpoint,api', [
    ('https://llm.example.internal/v1', 'openai-completions'),
    ('https://api.openai.com/v1', 'openai-responses'),
])
def test_real_pi_selects_custom_model_and_endpoint_without_a_model_request(tmp_path, application, endpoint, api):
    import selectors

    settings = environment(application) | {'OPENAI_BASE_URL': endpoint}
    selected = RUNTIME.select_runtime(ROOT, settings, 'worker')[3]
    resolved = resolve_harness_llm(ROOT, selected)
    command = PiRuntimeLocator(ROOT / '.grid-agent/runtime/pi', {},
                               runtime_lock=PiRuntimeLock.load(ROOT / 'configs/runtime/pi-runtime.lock.json')).resolve()
    paths = RuntimePaths(command=command, project_pi_dir=tmp_path / 'original-agent',
                         session_dir=tmp_path / 'session', workspace=tmp_path)
    launch = build_pi_launch(resolved, paths,
                             base_environment={'PATH': os.environ['PATH'], 'CAPABILITY_AGENT_PI_OFFLINE': '1'})
    process = subprocess.Popen(launch.argv, env=launch.environment, cwd=tmp_path,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True)
    try:
        assert process.stdin and process.stdout
        process.stdin.write('{"id":"inspect","type":"get_state"}\n')
        process.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            assert selector.select(timeout=20), 'Pi did not return its selected model state'
            response = json.loads(process.stdout.readline())
        assert response.get('success'), 'Pi rejected the configured custom model'
        model = response['data']['model']
        assert model['provider'] == 'openai'
        assert model['id'] == 'deepseek-flash'
        assert model['baseUrl'] == endpoint
        assert model['api'] == api
    finally:
        process.terminate()
        process.wait(timeout=10)
