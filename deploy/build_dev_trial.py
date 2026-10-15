"""Operator-only exact-source contexts and source-free trial bundles."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import posixpath
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

_contract_spec = importlib.util.spec_from_file_location('user_data_compatibility',
                                                     Path(__file__).with_name('user_data_compatibility.py'))
data_contract = importlib.util.module_from_spec(_contract_spec)
_contract_spec.loader.exec_module(data_contract)

BUNDLE_INPUTS = {'deploy/dev-trial/compose.yaml', 'deploy/dev-trial/start.sh',
                'deploy/dev-trial/capstone.sh', 'deploy/dev-trial/install.sh',
                'deploy/dev-trial/env.example', 'configs/llm-providers.json',
                'deploy/dev-trial/offline-validation-samples.txt'}


def _git(root: Path, *arguments: str) -> bytes:
    return subprocess.run(['git', '-C', str(root), *arguments], check=True,
                          capture_output=True, timeout=60).stdout


def _new_output(root: Path, output: Path) -> Path:
    root = root.resolve()
    output = Path(output.absolute())
    if output.exists() or any(path.is_symlink() for path in [output, *output.parents]):
        raise ValueError('Output must be new and must not pass through a symlink')
    try:
        output.relative_to(root)
    except ValueError:
        raise ValueError('Output must be inside the checkout') from None
    if subprocess.run(['git', '-C', str(root), 'check-ignore', '--quiet', str(output)],
                      capture_output=True).returncode:
        raise ValueError('Output must be ignored')
    return output


def stage_models(root: Path, context: Path, library: Path) -> dict:
    executable = root / 'packages/pypsa-agent/.venv/bin/python'
    if not executable.is_file() or not library.is_dir():
        raise ValueError('Prepare the managed PyPSA runtime and verified model library first')
    program = '''
import hashlib, json, shutil, sys
from pathlib import Path
context, library = map(Path, sys.argv[1:])
sys.path.insert(0, str(context / 'packages/pypsa-model-authority/src'))
from pypsa_model_authority.model_library import list_official_examples, verified_asset_path
assets = list_official_examples()
if len(assets) != 6: raise ValueError('six pinned model assets required')
stage = context / 'deploy/local-model-assets'
stage.mkdir(parents=True, exist_ok=True)
receipt = {}
for item in assets:
    source = verified_asset_path(item.catalog_id, root=library)
    shutil.copy2(source, stage / source.name)
    receipt[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
print(json.dumps(receipt, sort_keys=True))
'''
    environment = {key: value for key, value in os.environ.items()
                   if key in {'PATH', 'HOME', 'LANG', 'SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE'}}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run([str(executable), '-c', program, str(context), str(library)],
                            env=environment, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise ValueError('Pinned model asset verification failed')
    return json.loads(result.stdout)


def prepare_context(root: Path, revision: str, output: Path, model_library: Path | None = None) -> dict:
    root = root.resolve()
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Select an exact committed source revision')
    if _git(root, 'rev-parse', revision + '^{commit}').decode().strip() != revision:
        raise ValueError('Source revision differs')
    output = _new_output(root, output)
    selected = ['Dockerfile', '.dockerignore', 'packages', 'configs', 'validation', 'tools',
                'scripts', 'schemas', 'third-party-notices', 'deploy', 'pyproject.toml', 'uv.lock']
    selected.extend(name for name in _git(root, 'ls-tree', '--name-only', revision).decode().splitlines()
                    if '/' not in name and data_contract.selected(name) and name not in selected)
    archive = _git(root, 'archive', '--format=tar', revision, '--', *selected)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        for member in source.getmembers():
            path = Path(member.name)
            if member.issym():
                target = posixpath.normpath(posixpath.join(str(path.parent), member.linkname))
                if member.linkname.startswith('/') or target.startswith('../') or target == '..':
                    raise ValueError('Source archive contains an unsafe symlink')
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir() or member.issym()):
                raise ValueError('Source archive contains an unsafe entry')
        output.mkdir(parents=True, mode=0o700)
        source.extractall(output, filter='data')
    app = output / 'trial-app'
    spec = importlib.util.spec_from_file_location('trial_prepare_app', output / 'deploy/prepare_app_source.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.prepare_app_source(root, revision, 'local-dev', '', app)
    for original, destination in [('App.Dockerfile', 'Dockerfile'), ('Caddyfile', 'Caddyfile')]:
        shutil.copyfile(output / 'deploy/dev-trial' / original, app / destination)
    assets = stage_models(root, output, model_library or root / '.grid-agent/runtime/pypsa-models')
    inputs = BUNDLE_INPUTS | {'deploy/prepare_app_source.py'}
    if (output / 'deploy/dev-trial/install-version.sh').exists():
        inputs = inputs | {'deploy/dev-trial/install-version.sh'}
    if (output / 'deploy/dev-trial/install-offline.sh').exists():
        inputs = inputs | {'deploy/dev-trial/install-offline.sh'}
    if (output / 'deploy/dev-trial/offline-validation-samples.txt').exists():
        inputs = inputs | {'deploy/dev-trial/offline-validation-samples.txt'}
    (output / 'trial-context.json').write_text(json.dumps({'source_revision': revision,
        'data_inputs': {name: hashlib.sha256(content).hexdigest()
                        for name, content in data_contract.context_files(output).items()},
        'model_assets': assets, 'inputs': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                         for name in inputs}}, indent=2, sort_keys=True) + '\n')
    return {'source_revision': revision, 'backend_context': str(output), 'app_context': str(app)}


def verify_acceptance(revision: str, images: dict, platforms: list[str], acceptance: dict | None,
                      format_sha256: str) -> None:
    if (not isinstance(acceptance, dict) or acceptance.get('schema') != 'capstone-dev-trial-acceptance/1'
            or acceptance.get('source_revision') != revision or acceptance.get('images') != images
            or set(acceptance.get('platforms', {})) != set(platforms)):
        raise ValueError('Final bundle requires matching two-platform acceptance receipts')
    for receipt in acceptance['platforms'].values():
        if not isinstance(receipt, dict) or any(receipt.get(key) != 'passed'
                for key in ['readiness', 'cases', 'replay', 'restart', 'browser', 'anonymous_pull']):
            raise ValueError('Final platform acceptance is incomplete')
    metadata = acceptance.get('image_metadata', {})
    if set(metadata) != set(images):
        raise ValueError('Final acceptance requires all image metadata')
    for key, reference in images.items():
        item = metadata[key]
        if (not isinstance(item, dict) or item.get('reference') != reference or item.get('platforms') != platforms
                or (key in {'backend', 'app'} and item.get('source_revision') != revision)):
            raise ValueError('Final image acceptance differs from the source or platform manifests')
    data = acceptance.get('data_compatibility')
    if (not isinstance(data, dict) or data.get('source_revision') != revision
            or data.get('format_sha256') != format_sha256
            or not isinstance(data.get('previous_source_revisions'), list)
            or not data['previous_source_revisions']
            or any(not isinstance(item, str) or item == revision or not re.fullmatch(r'[a-f0-9]{40}', item)
                   for item in data['previous_source_revisions'])
            or any(data.get(key) != 'passed' for key in ['upgrade', 'read', 'replay', 'rollback'])):
        raise ValueError('Final data compatibility acceptance is incomplete or differs from the descriptor')


def write_bundle(source: Path, output: Path, revision: str, images: dict,
                 platforms: list[str], *, candidate: bool = False, acceptance: dict | None = None) -> dict:
    if output.exists() or output.is_symlink():
        raise ValueError('Bundle output already exists')
    if not re.fullmatch(r'[a-f0-9]{40}', revision) or set(images) != {'backend', 'app', 'postgres', 'objects'}:
        raise ValueError('Bundle requires an exact source and four images')
    receipt = json.loads((source / 'trial-context.json').read_text())
    if receipt.get('source_revision') != revision:
        raise ValueError('Bundle source differs from its prepared context')
    inputs = receipt.get('inputs', {})
    required = BUNDLE_INPUTS.copy()
    if ('deploy/dev-trial/install-version.sh' in inputs
            or (source / 'deploy/dev-trial/install-version.sh').exists()):
        required.add('deploy/dev-trial/install-version.sh')
    if not required <= inputs.keys() or any(
            not (source / name).is_file() or (source / name).is_symlink()
            or hashlib.sha256((source / name).read_bytes()).hexdigest() != inputs[name] for name in required):
        raise ValueError('Bundle inputs differ from the exact source context')
    if candidate:
        if platforms not in [['linux/amd64'], ['linux/arm64']]:
            raise ValueError('Candidate must select one validation platform')
    elif platforms != ['linux/amd64', 'linux/arm64'] or not all(
            re.fullmatch(r'[a-z0-9][a-z0-9._:/-]*@sha256:[a-f0-9]{64}', value) for value in images.values()):
        raise ValueError('Published bundle requires both platforms and exact image digests')
    descriptor = data_contract.generate_descriptor(source, revision, images)
    data_inputs = {name: hashlib.sha256(content).hexdigest()
                   for name, content in data_contract.context_files(source).items()}
    if receipt.get('data_inputs') != data_inputs:
        raise ValueError('Frozen persistence inputs differ from the source context receipt')
    if not candidate:
        verify_acceptance(revision, images, platforms, acceptance,
                          descriptor['CAPSTONE_DATA_FORMAT_SHA256'])
    output.mkdir(parents=True, mode=0o700)
    for name in ['compose.yaml', 'start.sh', 'capstone.sh', 'install.sh']:
        shutil.copyfile(source / 'deploy/dev-trial' / name, output / name)
    for name in ['start.sh', 'capstone.sh', 'install.sh']:
        (output / name).chmod(0o755)
    (output / 'data-contract.env').write_text(data_contract.render_descriptor(descriptor))
    registry = json.loads((source / 'configs/llm-providers.json').read_text())
    settings = (source / 'deploy/dev-trial/env.example').read_text().replace(
        '@OPENAI_DEFAULT_MODEL@', registry['providers']['openai']['default_model'])
    for name in ['.env', '.env.example']:
        (output / name).write_text(settings)
    document = {'schema': 'capstone-dev-trial/1', 'channel': 'dev-trial-candidate' if candidate else 'dev-trial',
                'source_revision': revision, 'platforms': platforms, 'images': images}
    (output / 'manifest.json').write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
    names = {'backend': 'BACKEND', 'app': 'APP', 'postgres': 'POSTGRES', 'objects': 'OBJECTS'}
    (output / 'release.env').write_text(''.join('CAPSTONE_' + names[key] + '_IMAGE=' + value + '\n'
                                              for key, value in images.items())
                                      + 'CAPSTONE_TRIAL_PLATFORM=' + (platforms[0] if candidate else '') + '\n')
    (output / 'README.txt').write_text(
        'Capstone temporary dev trial\nSource: ' + revision + '\n'
        'Preinstalled example grids are included. Start with pandapower IEEE39.\n'
        'Requires Docker Engine or Docker Desktop with Docker Compose v2.\n'
        'Linux and macOS: set DEEPSEEK_API_KEY in the startup environment, then run ./start.sh.\n'
        'Edit .env to change Provider/model or the App port. OpenAI example is in comments.\n'
        'Startup environment values override .env. Do not put keys in shell command arguments.\n'
        'Run ./start.sh status, ./start.sh logs or ./start.sh stop. Stop preserves all data.\n'
        'Keep the original directory and .capstone-trial private configuration.\n'
        'Use a separate CAPSTONE_INSTANCE starting with capstone-user- for another instance.\n'
        'Windows WSL2 is a target; it has not been verified. This is not a stable release.\n')
    with (output / 'README.txt').open('a') as notes:
        notes.write('Manage versions with ./capstone.sh. The frozen ./start.sh runs this version.\n'
                    'The data contract blocks unverified backend and dependency changes.\n'
                    'It does not replace migration tests or tests with old data.\n'
                    + ('Candidate: full data compatibility has not been accepted.\n' if candidate else '')
                    + '\nOptional PyPSA examples: AC-DC Meshed, Storage-HVDC, SciGrid-DE, '
                    'Model-Energy, Stochastic-Network and Carbon Management.\n'
                    'Regional Six Bus is also included; select another grid when needed.\n')
    samples = (source / 'deploy/dev-trial/offline-validation-samples.txt').read_text()
    (output / 'README.md').write_text(
        '# Capstone 在线安装使用说明\n\n'
        '源提交：`' + revision + '`。这是开发试用包。\n\n'
        '已预装示例电网，默认使用 pandapower 的 IEEE39 电网。'
        '建议先按下方案例体验，再按需切换其他电网。\n\n'
        '## 安装前提\n\n'
        '需要 Docker Engine 或 Docker Desktop，以及 Docker Compose v2。'
        '在线安装器需要联网下载部署包、版本目录和四类固定摘要镜像；'
        'Docker 必须能够访问交付包指定的镜像仓库。安装过程不需要本地源码。\n\n'
        '按下方步骤配置模型接口并运行在线安装器。默认安装目录为 `$HOME/capstone`，'
        '可通过 `CAPSTONE_TRIAL_DIRECTORY` 选择其他目录。'
        '默认 App 地址为 <http://127.0.0.1:19173/>。\n\n'
        '## 配置模型接口\n\n'
        '在线包的默认配置仍为 `CAPSTONE_PUBLIC_PROVIDER=deepseek`、'
        '`CAPSTONE_PUBLIC_MODEL=deepseek-flash`，使用启动环境中的 `DEEPSEEK_API_KEY`。\n\n'
        '使用内网 OpenAI 兼容接口时，将以下配置写入安装目录的 `.env`，'
        '替换示例地址和模型名。`PROVIDER` 和 `OPENAI_MODEL` 优先于原有 CAPSTONE 配置：\n\n'
        '```dotenv\nPROVIDER=openai\nOPENAI_BASE_URL=http://your-internal-llm:8000/v1\n'
        'OPENAI_MODEL=deepseek-flash\nCAPSTONE_APP_PORT=19173\n```\n\n'
        '首次安装前还没有 `.env` 时，可在运行安装器的同一终端设置这些非密钥变量：\n\n'
        '```sh\nexport PROVIDER=openai\nexport OPENAI_BASE_URL=http://your-internal-llm:8000/v1\n'
        'export OPENAI_MODEL=deepseek-flash\n```\n\n'
        '在启动环境中设置 `OPENAI_API_KEY`。例如在 Bash 中交互输入，'
        '避免将密钥写入命令历史或参数：\n\n'
        '```bash\nread -r -s -p "OPENAI_API_KEY: " OPENAI_API_KEY\nprintf "\\n"\n'
        'export OPENAI_API_KEY\n```\n\n'
        '首次安装时，在同一终端执行：\n\n'
        '```sh\ncurl -fsSL https://raw.githubusercontent.com/uukuguy/capstone/dev/deploy/dev-trial/install.sh | sh\n```\n\n'
        '已安装时，使用下方管理命令启动服务。\n\n'
        '自定义 OpenAI 地址使用 Chat Completions 协议；'
        '官方 `https://api.openai.com/v1` 保持 Responses 协议。'
        '启动环境优先于 `.env`。密钥只供后端使用，不放入 App 配置、截图或报告。'
        '更换安装目录时，将示例命令中的 `$HOME/capstone` 改为实际目录。\n\n'
        '## 启动、停止和版本管理\n\n'
        '```sh\nsh "$HOME/capstone/capstone.sh" start\n'
        'sh "$HOME/capstone/capstone.sh" status\nsh "$HOME/capstone/capstone.sh" logs\n'
        'sh "$HOME/capstone/capstone.sh" stop\nsh "$HOME/capstone/capstone.sh" versions\n```\n\n'
        '用 `use <Git提交>` 切换已安装版本；用 `install <Git提交>` 在线安装版本。'
        '版本切换受数据兼容检查保护。停止保留数据；重新启动仍需提供所选接口的密钥。'
        '原始 `README.txt` 和各版本目录中的说明保留供兼容入口使用。\n\n'
        '## 数据和备份\n\n'
        '保留完整安装目录，包括 `.env`、`.capstone-management`、`versions` 下的私有状态和安装凭据。'
        '数据库及对象存储数据位于 Docker volumes，单独复制安装目录不构成完整备份。'
        '备份前先停止服务，再按 Docker 运维流程备份本安装的数据库、对象存储 volumes 和安装目录；'
        '恢复时保持它们来自同一备份。不要删除 volumes、修改数据兼容标记或覆盖其他安装的数据。\n\n'
        '## 可复制的测试案例\n\n'
        '以下案例与离线包共用同一份源文件。需要模型接口可用，可能产生 Provider 费用。'
        '按案例说明选择模型、建立新对话并逐轮发送。\n\n```text\n'
        + samples.rstrip() + '\n```\n\n'
        '## 可选电网示例\n\n'
        '需要其他电网时，可在模型目录中切换。PyPSA示例包括AC-DC Meshed、Storage-HVDC、'
        'SciGrid-DE、Model-Energy、Stochastic-Network及Carbon Management；'
        '区域六母线等内置电网也随程序提供。\n')
    (output / 'README.md').chmod(0o644)
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model-library', type=Path)
    parser.add_argument('--image-manifest', type=Path)
    parser.add_argument('--bundle-output', type=Path)
    parser.add_argument('--candidate-platform', choices=('linux/amd64', 'linux/arm64'))
    parser.add_argument('--acceptance', type=Path)
    arguments = parser.parse_args()
    try:
        context = prepare_context(arguments.root, arguments.source_revision, arguments.output,
                                  arguments.model_library)
        if arguments.image_manifest or arguments.bundle_output:
            if not arguments.image_manifest or not arguments.bundle_output:
                raise ValueError('Image manifest and bundle output must be supplied together')
            identity = json.loads(arguments.image_manifest.read_text())
            if identity.get('source_revision') != arguments.source_revision:
                raise ValueError('Image manifest source differs')
            output = _new_output(arguments.root, arguments.bundle_output)
            acceptance = json.loads(arguments.acceptance.read_text()) if arguments.acceptance else None
            write_bundle(Path(context['backend_context']), output, arguments.source_revision, identity['images'],
                         [arguments.candidate_platform] if arguments.candidate_platform else ['linux/amd64', 'linux/arm64'],
                         candidate=bool(arguments.candidate_platform), acceptance=acceptance)
            context['bundle_output'] = str(output)
        print(json.dumps(context))
    except (OSError, ValueError, subprocess.SubprocessError):
        parser.exit(1, 'Trial preparation failed: select an exact source and new ignored output.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
