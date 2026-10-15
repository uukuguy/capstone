"""Export four existing Linux AMD64 images with a frozen source-free deployment."""
from __future__ import annotations

import argparse
import gzip
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import zlib

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


def read_archive_identity(path: Path, kind: str, tag: str, revision: str) -> dict:
    """Verify the tagged save's manifest, config and complete layer chain."""
    with tarfile.open(path) as archive:
        names = [member.name for member in archive.getmembers()]
        if len(names) != len(set(names)):
            raise ValueError('Offline image archive contains duplicate members')

        def regular_member(name):
            try:
                member = archive.getmember(name)
            except KeyError:
                raise ValueError('Offline image archive member is missing') from None
            if not member.isfile():
                raise ValueError('Offline image archive member is not regular')
            return member

        def document(name):
            member = regular_member(name)
            if member.size > 1024 * 1024:
                raise ValueError('Offline image metadata is invalid')
            return archive.extractfile(member).read()

        def descriptor(value):
            digest = value.get('digest', '')
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
                raise ValueError('Offline image descriptor is invalid')
            raw = document('blobs/sha256/' + digest[7:])
            if hashlib.sha256(raw).hexdigest() != digest[7:] or len(raw) != value.get('size'):
                raise ValueError('Offline image descriptor checksum differs')
            return json.loads(raw)

        legacy = json.loads(document('manifest.json'))
        if len(legacy) != 1 or legacy[0].get('RepoTags') != [tag]:
            raise ValueError('Offline image archive tag differs')
        node = json.loads(document('index.json'))
        tag_bound = False
        for _ in range(5):
            entries = node.get('manifests', [])
            if len(entries) != 1:
                raise ValueError('Offline archive must contain one image platform')
            entry = entries[0]
            annotations = entry.get('annotations', {})
            tag_bound |= annotations.get('io.containerd.image.name') in {tag, 'docker.io/' + tag}
            node = descriptor(entry)
            if entry.get('mediaType') in {
                'application/vnd.oci.image.manifest.v1+json',
                'application/vnd.docker.distribution.manifest.v2+json',
            }:
                break
            if entry.get('mediaType') not in {
                'application/vnd.oci.image.index.v1+json',
                'application/vnd.docker.distribution.manifest.list.v2+json',
            }:
                raise ValueError('Offline image manifest type is invalid')
        else:
            raise ValueError('Offline image index is too deep')
        if not tag_bound:
            raise ValueError('Offline OCI archive tag differs')
        config_descriptor = node.get('config', {})
        config = descriptor(config_descriptor)
        config_digest = config_descriptor['digest']
        if legacy[0].get('Config') != 'blobs/sha256/' + config_digest[7:]:
            raise ValueError('Offline manifest and config relationship differs')
        if config.get('os') != 'linux' or config.get('architecture') != 'amd64':
            raise ValueError('Offline image archive platform must be linux/amd64')
        if kind in {'backend', 'app'} and config.get('config', {}).get('Labels', {}).get(
                'org.opencontainers.image.revision') != revision:
            raise ValueError('Offline image archive source differs')
        layers = node.get('layers')
        legacy_layers = legacy[0].get('Layers')
        rootfs = config.get('rootfs')
        if not isinstance(rootfs, dict) or rootfs.get('type') != 'layers':
            raise ValueError('Offline image root filesystem is invalid')
        diff_ids = rootfs.get('diff_ids')
        if (not all(isinstance(value, list) for value in [layers, legacy_layers, diff_ids])
                or len(layers) != len(legacy_layers) or len(layers) != len(diff_ids)):
            raise ValueError('Offline image layer chain differs')
        raw_types = {'application/vnd.oci.image.layer.v1.tar', 'application/vnd.docker.image.rootfs.diff.tar'}
        gzip_types = {'application/vnd.oci.image.layer.v1.tar+gzip', 'application/vnd.docker.image.rootfs.diff.tar.gzip'}
        for layer, legacy_path, diff_id in zip(layers, legacy_layers, diff_ids):
            if not isinstance(layer, dict):
                raise ValueError('Offline image layer descriptor is invalid')
            digest = layer.get('digest', '')
            if (not isinstance(digest, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest)
                    or not isinstance(diff_id, str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', diff_id)):
                raise ValueError('Offline image layer digest is invalid')
            name = 'blobs/sha256/' + digest[7:]
            if legacy_path != name:
                raise ValueError('Offline OCI and Docker layer order differs')
            member = regular_member(name)
            if member.size != layer.get('size'):
                raise ValueError('Offline image layer size differs')
            media_type = layer.get('mediaType')
            if media_type not in raw_types | gzip_types:
                raise ValueError('Offline image layer codec is unsupported')
            encoded_hash = hashlib.sha256()
            with archive.extractfile(member) as source:
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    encoded_hash.update(block)
            if 'sha256:' + encoded_hash.hexdigest() != digest:
                raise ValueError('Offline image layer checksum differs')
            decoded_hash = encoded_hash
            if media_type in gzip_types:
                decoded_hash = hashlib.sha256()
                try:
                    with archive.extractfile(member) as source, gzip.GzipFile(fileobj=source) as decoded:
                        for block in iter(lambda: decoded.read(1024 * 1024), b''):
                            decoded_hash.update(block)
                except (OSError, EOFError, zlib.error):
                    raise ValueError('Offline image gzip layer is invalid') from None
            if 'sha256:' + decoded_hash.hexdigest() != diff_id:
                raise ValueError('Offline image layer does not match rootfs diff_ids')
        return {'kind': kind, 'tag': tag, 'config_digest': config_digest,
                'manifest_digest': entry['digest'], 'platform': 'linux/amd64'}


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
    sample_path = 'deploy/dev-trial/offline-validation-samples.txt'
    if checksum(context / sample_path) != receipt.get('inputs', {}).get(sample_path):
        raise ValueError('Offline usage samples differ from the frozen context')
    samples = (context / sample_path).read_text()
    source_ids = {}
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
        source_ids[kind] = identity
    output.mkdir(parents=True, mode=0o700)
    records = []
    for kind in KINDS:
        tag = 'capstone-offline/' + kind + ':' + revision
        subprocess.run(['docker', 'image', 'tag', source_ids[kind], tag], check=True)
        path = output / (kind + '.tar')
        subprocess.run(['docker', 'image', 'save', '--output', str(path), tag], check=True)
        records.append(read_archive_identity(path, kind, tag, revision))
    identities = {row['kind']: row['config_digest'] for row in records}
    builder = _builder()
    # A separate offline channel keeps online dual-platform acceptance unchanged.
    deployment = output / 'deployment'
    document = builder.write_bundle(context, deployment, revision, identities, ['linux/amd64'], candidate=True)
    document['channel'] = 'dev-trial-offline'
    document['offline_image_identities'] = records
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
        '保留安装目录、私有配置及数据卷；兼容检查拒绝未验证的数据切换。\n\n' + samples)
    archive = output / 'deployment.tar.gz'
    with tarfile.open(archive, 'w:gz') as target:
        for path in sorted(deployment.iterdir()):
            target.add(path, arcname=path.name, recursive=False)
    for path in deployment.iterdir():
        path.unlink()
    deployment.rmdir()
    (output / 'images.tsv').write_text(''.join(
        '\t'.join([row['kind'], row['tag'], row['config_digest'], row['manifest_digest'],
                   row['platform'], row['kind'] + '.tar']) + '\n' for row in records))
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
        '4. 安装后试用\n' + samples + '\n'
        '5. 数据与排错\n'
        '在线和离线安装都将用户数据保存在安装机器：PostgreSQL卷postgres-data保存\n'
        '对话及任务记录，object-data保存报告、结果和证据；api-runs、worker-runs、\n'
        'pypsa-runs保存运行文件。实际卷名带安装实例前缀，由Docker管理。\n'
        '备份须同时包含安装目录及上述数据卷；仅复制$HOME/capstone不能完整恢复。\n'
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
    except (OSError, ValueError, KeyError, tarfile.TarError, subprocess.SubprocessError):
        parser.exit(1, 'Offline export failed. Check the frozen source and four local AMD64 images.\n')


if __name__ == '__main__':
    main()
