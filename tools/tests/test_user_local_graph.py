import importlib.util
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHA = 'a' * 40
VERSION = 'user-local-' + SHA[:7]
URL = 'https://github.com/uukuguy/capstone/releases/tag/' + VERSION


def renderer():
    spec = importlib.util.spec_from_file_location('overview', ROOT / 'tools/render_project_overview.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def document(identity='trial', sha=SHA, version=VERSION, url=URL, status='已验证可安装'):
    return ('## 用户自安装试用版本\n'
            '| ID | 精确Git提交 | 版本 | 发布地址 | 安装命令 | 验收状态 |\n'
            '| --- | --- | --- | --- | --- | --- |\n'
            f'| {identity} | `{sha}` | `{version}` | {url} | `install --name "<trial>"` | {status} |\n')


def test_trial_bound_to_exact_node_source():
    nodes = [{'id': 'trial', 'sha': SHA}]
    renderer().bind_user_local_trials(document(), nodes)
    assert nodes[0]['trial'] == dict(sha=SHA, version=VERSION, release_url=URL,
                                    command='install --name "<trial>"', status='已验证可安装',
                                    installable=True)


@pytest.mark.parametrize('fields', [
    {'identity': 'unknown'}, {'sha': 'b' * 40}, {'sha': SHA[:7]},
    {'version': 'user-local-bbbbbbb'}, {'version': 'user-local-' + SHA[:6]},
    {'url': 'javascript:alert(1)'}, {'url': 'https://github.com.evil/uukuguy/capstone/releases/tag/' + VERSION},
    {'url': URL + '?redirect=evil'}, {'url': URL.replace(VERSION, 'user-local-bbbbbbb')},
    {'url': URL.replace('uukuguy', 'other')},
])
def test_invalid_source_or_release_is_rejected(fields):
    with pytest.raises(ValueError):
        renderer().bind_user_local_trials(document(**fields), [{'id': 'trial', 'sha': SHA}])


@pytest.mark.parametrize('status', ['待验证', '已验证', '已验证可安装（待发布）'])
def test_pending_status_has_metadata_without_installability(status):
    nodes = [{'id': 'trial', 'sha': SHA}]
    renderer().bind_user_local_trials(document(status=status), nodes)
    assert nodes[0]['trial']['installable'] is False


def test_missing_section_supports_old_snapshots():
    nodes = [{'id': 'trial', 'sha': SHA}]
    renderer().bind_user_local_trials('## Other\n', nodes)
    assert nodes[0]['trial'] is None


def test_full_sha_version_is_supported():
    version = 'user-local-' + SHA
    nodes = [{'id': 'trial', 'sha': SHA}]
    renderer().bind_user_local_trials(document(version=version, url=URL.replace(VERSION, version)), nodes)
    assert nodes[0]['trial']['installable'] is True


def test_present_section_requires_table_columns():
    with pytest.raises(ValueError):
        renderer().bind_user_local_trials('## 用户自安装试用版本\n', [{'id': 'trial', 'sha': SHA}])


def test_duplicate_trial_is_rejected():
    text = document()
    with pytest.raises(ValueError):
        renderer().bind_user_local_trials(text + text.splitlines()[-1] + '\n', [{'id': 'trial', 'sha': SHA}])


def test_rendered_marker_is_accessible_and_escaped():
    template = (ROOT / 'tools/project_overview/template.html').read_text()
    assert "+trialLink(n)+" in template
    esc = re.search(r'^const esc=.*$', template, re.M).group()
    helper = re.search(r'^function trialLink\(n\)\{.*?^\}', template, re.M | re.S)
    assert helper is not None, 'Missing install link renderer'
    nodes = [{'id': 'trial', 'sha': SHA}]
    renderer().bind_user_local_trials(document(), nodes)
    node = nodes[0]
    script = esc + '\n' + helper.group() + '\nconst n=' + json.dumps(node) + ';\n'
    script += '''console.log(JSON.stringify([trialLink(n),
        trialLink({...n, trial: {...n.trial, installable: false}}),
        trialLink({...n, trial: {...n.trial, release_url: 'javascript:alert(1)'}}),
        trialLink({...n, sha: 'b'.repeat(40)}), trialLink({sha: n.sha})]));'''
    marker, *absent = json.loads(subprocess.check_output(['node', '-e', script], text=True))
    assert absent == ['', '', '', '']
    assert f'href="{URL}"' in marker
    assert 'target="_blank"' in marker and 'rel="noopener noreferrer"' in marker
    assert 'aria-label="用户自安装试用已验证可安装' in marker
    assert 'title="用户自安装试用已验证可安装' in marker
    assert VERSION in marker and SHA in marker
    assert '<svg' in marker and 'aria-hidden="true"' in marker
    assert '&quot;&lt;trial&gt;&quot;' in marker
    assert '"<trial>"' not in marker
