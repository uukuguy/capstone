"""Export four existing Linux AMD64 images with a frozen source-free deployment."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

KINDS = ('backend', 'app', 'postgres', 'objects')


def _builder():
    spec = importlib.util.spec_from_file_location('offline_trial_builder', Path(__file__).with_name('build_dev_trial.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def export_bundle(context: Path, output: Path, revision: str, images: dict) -> dict:
    if (not re.fullmatch(r'[a-f0-9]{40}', revision) or set(images) != set(KINDS)
            or output.exists() or any(p.is_symlink() for p in [output, *output.parents])):
        raise ValueError('Select an exact source, four images and a new output')
    receipt = json.loads((context / 'trial-context.json').read_text())
    if receipt.get('source_revision') != revision:
        raise ValueError('Offline context source differs')
    # Transport scripts must also come from the frozen context.
    for name in ['install-offline.sh', 'install-version.sh']:
        path = 'deploy/dev-trial/' + name
        if checksum(context / path) != receipt.get('inputs', {}).get(path):
            raise ValueError('Offline installer differs from the frozen context')
    identities = {}
    for kind in KINDS:
        result = subprocess.run(['docker', 'image', 'inspect', images[kind]], check=True,
                                capture_output=True, text=True)
        metadata = json.loads(result.stdout)[0]
        if metadata.get('Os') != 'linux' or metadata.get('Architecture') != 'amd64':
            raise ValueError('Offline image platform must be linux/amd64')
        if kind in {'backend', 'app'} and metadata.get('Config', {}).get('Labels', {}).get(
                'org.opencontainers.image.revision') != revision:
            raise ValueError('Offline image source differs')
        identity = metadata.get('Id', '')
        if not re.fullmatch(r'sha256:[a-f0-9]{64}', identity):
            raise ValueError('Offline image ID is invalid')
        identities[kind] = identity
    builder = _builder()
    # A separate offline channel keeps online dual-platform acceptance unchanged.
    deployment = output / 'deployment'
    document = builder.write_bundle(context, deployment, revision, identities, ['linux/amd64'], candidate=True)
    document['channel'] = 'dev-trial-offline'
    (deployment / 'manifest.json').write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
    settings = ('# Keep OPENAI_API_KEY in the startup environment.\n'
                'PROVIDER=openai\nOPENAI_MODEL=deepseek-flash\nOPENAI_BASE_URL=\n'
                'CAPSTONE_APP_PORT=19173\n')
    for name in ['.env', '.env.example']:
        (deployment / name).write_text(settings)
    # Config IDs intentionally give storage a conservative new data identity.
    # The existing data guard must block upgrades from unverified registry refs.
    (deployment / 'install.sh').write_text('#!/bin/sh\nprintf "%s\\n" "Use the original offline package install-offline.sh to install a version." >&2\nexit 1\n')
    (deployment / 'README.txt').write_text(
        'Capstone 离线安装管理\n源码：' + revision + '\n'
        'Linux AMD64；须预装Docker Engine及Compose v2。模型已在镜像中。\n'
        '默认PROVIDER=openai、OPENAI_MODEL=deepseek-flash。\n'
        '在.env设置OPENAI_BASE_URL/API前缀及模型；启动环境提供OPENAI_API_KEY。\n'
        '自定义地址使用Chat Completions；地址必须能从容器访问。\n'
        '用sh capstone.sh start/status/logs/stop/versions管理；stop保留数据。\n'
        '保留安装目录、私有配置及数据卷；兼容检查拒绝未验证的数据切换。\n')
    archive = output / 'deployment.tar.gz'
    with tarfile.open(archive, 'w:gz') as target:
        for path in sorted(deployment.iterdir()):
            target.add(path, arcname=path.name, recursive=False)
    for path in deployment.iterdir():
        path.unlink()
    deployment.rmdir()
    (output / 'images.tsv').write_text(''.join(f'{kind}\t{identities[kind]}\tlinux/amd64\t{kind}.tar\n' for kind in KINDS))
    for kind in KINDS:
        subprocess.run(['docker', 'image', 'save', '--output', str(output / (kind + '.tar')), identities[kind]], check=True)
    version = 'user-local-' + revision[:12]
    script = (context / 'deploy/dev-trial/install-version.sh').read_text()
    for key, value in {'@VERSION@': version, '@ARCHIVE_URL@': 'offline', '@ARCHIVE_SHA256@': checksum(archive), '@SOURCE_REVISION@': revision}.items():
        script = script.replace(key, value)
    (output / 'install-version.sh').write_text(script)
    shutil.copyfile(context / 'deploy/dev-trial/install-offline.sh', output / 'install-offline.sh')
    (output / 'versions.tsv').write_text(f'{revision}\t{version}\thttps://github.com/uukuguy/capstone/releases/download/{version}/install.sh\t{checksum(output / "install-version.sh")}\t{date.today().isoformat()}\n')
    (output / 'manifest.json').write_text(json.dumps(document, indent=2, sort_keys=True) + '\n')
    (output / 'README.txt').write_text(
        'Capstone 用户离线安装（Linux AMD64）\n源码：' + revision + '\n\n'
        '1. 前提与校验\n'
        '预装Docker Engine、Docker Compose v2，并确认当前用户能运行docker。\n'
        '完整包包含四类镜像及六个模型文件，安装不访问公网；运行时须能访问内网LLM。\n'
        '在交付文件目录执行 sha256sum -c <交付归档名>.sha256，再解压.tar.gz。\n'
        '保留全部解压文件；安装器自动按SHA256SUMS逐项校验。\n\n'
        '2. 配置并安装（在Bash中执行）\n'
        '进入解压目录，替换地址和模型名；Key由用户输入，不写进脚本：\n'
        '  export PROVIDER=openai\n'
        '  export OPENAI_BASE_URL="http://你的内网LLM地址/v1"\n'
        '  export OPENAI_MODEL="deepseek-flash"\n'
        '  read -rsp "OPENAI_API_KEY: " OPENAI_API_KEY; echo; export OPENAI_API_KEY\n'
        '  sh install-offline.sh\n'
        '默认Provider为openai，模型为deepseek-flash；地址及Key必须由用户配置。\n'
        '地址填写API前缀，不包含/chat/completions；必须能从容器访问。\n'
        '容器内localhost指容器本身。自定义地址使用Chat Completions（流式及工具调用）；\n'
        '官方OpenAI地址保留Responses。服务需支持所选模型及工具调用。\n\n'
        '3. 访问与管理\n'
        '默认目录：$HOME/capstone；默认网页：http://127.0.0.1:19173/。\n'
        '远程Linux可从本机建立SSH转发：ssh -L 19173:127.0.0.1:19173 用户@服务器。\n'
        '  sh "$HOME/capstone/capstone.sh" status\n'
        '  sh "$HOME/capstone/capstone.sh" logs\n'
        '  sh "$HOME/capstone/capstone.sh" stop\n'
        '  sh "$HOME/capstone/capstone.sh" start\n'
        '新终端启动前须重新提供OPENAI_API_KEY。地址/模型/端口可写入安装目录.env；\n'
        '进程环境变量优先。安装前可export CAPSTONE_TRIAL_DIRECTORY选择其他目录，\n'
        'export CAPSTONE_APP_PORT选择其他端口。离线升级仍使用新的完整离线包。\n\n'
        '4. 整体验证\n'
        '运行status确认服务就绪；打开网页，新建对话，发送“仅回复：连接正常”。\n'
        '收到模型实际回复后，再做下面的专业验证；仅网页可打开不代表LLM已连通。\n'
        '完成样例后stop再start，刷新原对话，确认答案及分析过程仍可查看。\n\n'
        '5. 专用验证样例\n'
        '每个样例新建独立对话并选择对应模型；逐条发送，等待上一轮完成。\n'
        'A. pandapower / ieee39（IEEE-39）\n'
        '  ① 打开 IEEE-39 网络并解析线路 11 的端点。\n'
        '  ② 沿用已打开的网络执行一次交流潮流。\n'
        '  ③ 沿用当前潮流结果列出负载率最高的三条线路。\n'
        '检查：专业工具确实运行；潮流结果和排序来自本轮计算，带结果/证据引用。\n'
        'B. PyPSA / regional-six-bus（区域负荷增长）\n'
        '  ① 打开区域六母线模型，检查网络结构，并求解基准情景的固定容量调度。\n'
        '  ② 沿用刚才的模型，把 central-demand 在三个时段的负荷各增加 10 MW；保留基准情景，建立增长情景模型修订。\n'
        '  ③ 求解增长情景，比较两次求解状态、模型运行成本目标和发电安排，说明结论的适用边界，并给出本轮证据。\n'
        '检查：基准与增长情景分开，实际求解且有当前运行的结果和证据。\n'
        'C. PyPSA / pypsa-example/ac_dc_meshed（AC/DC结构）\n'
        '  ① 打开已登记的 AC/DC 示例网络，核对来源、AC/DC 母线以及 Line 和 Link 组件数量。\n'
        '  ② 沿用这个模型，按端点母线的 AC/DC 类型说明 Line 与 Link 组件的连接，并标明拓扑预览的范围。\n'
        '  ③ 基于已核查的结构，说明后续潮流研究还需要哪些工况与约束；不要把连接关系说成功率流或输电能力结论。\n'
        '检查：结构核查有来源引用；不将拓扑连接误说成已求解的潮流或输电能力。\n'
        '样例通过需同时有正常回答、实际专业工具和可回看的当前运行证据；\n'
        '示例用于安装与功能验证，不代替工程决策或用户业务验收。\n\n'
        '6. 数据与排错\n'
        'stop及重复安装保留数据和私有配置；请保留安装目录及Docker数据卷。\n'
        '缺地址/Key、校验失败或数据不兼容时会拒绝切换并保留原服务。\n'
        '不要删除数据卷绕过兼容检查；新独立试用可另选目录及端口。\n'
        '401先核对Key，模型错误核对OPENAI_MODEL，连接失败检查容器到接口的网络。\n')
    names = ['deployment.tar.gz', 'images.tsv', 'versions.tsv', 'manifest.json', 'install-version.sh', 'install-offline.sh', 'README.txt'] + [kind + '.tar' for kind in KINDS]
    (output / 'SHA256SUMS').write_text(''.join(checksum(output / name) + '  ' + name + '\n' for name in names))
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--context', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--image-manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        identity = json.loads(args.image_manifest.read_text())
        if identity.get('source_revision') != args.source_revision:
            raise ValueError('Image source differs')
        output = _builder()._new_output(args.root, args.output)
        document = export_bundle(args.context, output, args.source_revision, identity['images'])
        print(json.dumps({'output': str(output), 'manifest': document, 'checksums_sha256': checksum(output / 'SHA256SUMS')}))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        parser.exit(1, 'Offline export failed. Check the frozen source and four local AMD64 images.\n')


if __name__ == '__main__':
    main()
