"""Operator-only transport of published resource pins and verified package bytes.

Paths are trusted operator inputs, never public task or HTTP parameters. Applying
several resources is sequential: earlier successful installs remain if a later
verification fails. No application receipt is written for a partial application.
"""
import io
import json
import os
from pathlib import Path
import stat
import tarfile
import tempfile
from uuid import uuid4

from .application_capacity import limits
from .managed_resource_installation import InstallRequest, InstallationError
from .managed_resource_manifest import canonical, content_digest, relative_path, validate_manifest
from .managed_resources import ResourceConflict


def _request(value):
    # RuntimeSpec admits reference identifiers only. Binding files and values
    # remain target-owned and are never transported as package inputs.
    return InstallRequest.from_dict(value)


def _document(service, principal, workspace, profile):
    store = service.store
    draft = store.preinstall_manifest(principal, workspace, profile)
    manifest = store.published_manifest(principal, workspace, profile, draft['version'])
    entries = {}
    for entry in manifest['entries']:
        item = store.get_resource(principal, workspace, entry['resource_id'], entry['version'])
        if 'installation' not in item:
            raise InstallationError('resource_bundle_installation_spec_missing')
        spec = dict(item['installation'])
        if entry['resource']['kind'] == 'mcp_remote':
            spec['source'] = entry['resource']['source']
        request = _request(spec)
        if request.kind != entry['resource']['kind'] or request.source.__dict__ != entry['resource']['source']:
            raise InstallationError('resource_bundle_source_mismatch')
        entries[entry['resource_id']] = {'request': request.to_dict(),
            'publication': service.installer.publication(entry['resource']['digest'])}
        if len(canonical(entries).encode()) > limits.control_document_bytes:
            raise InstallationError('resource_bundle_metadata_limit')
    return {'schema': 'capstone-preinstall-bundle/1', 'manifest': manifest, 'entries': entries}


def export_bundle(service, principal, workspace, profile, destination_path):
    """Write a new bounded tar; never overwrite an existing operator file."""
    document = _document(service, principal, workspace, profile)
    raw = canonical(document).encode()
    if len(raw) > limits.control_document_bytes:
        raise InstallationError('resource_bundle_metadata_limit')
    destination = Path(destination_path)
    count = total = 0
    # A private temporary output avoids leaving a partial bundle at destination.
    with tempfile.TemporaryDirectory(prefix='.resource-bundle-', dir=destination.parent) as temporary:
        archive_path = Path(temporary) / 'bundle.tar'
        with tarfile.open(archive_path, 'w') as archive:
            info = tarfile.TarInfo('bundle.json'); info.size = len(raw); info.mode = 0o600
            archive.addfile(info, io.BytesIO(raw))
            for entry in document['manifest']['entries']:
                resource = entry['resource']
                if resource['kind'] == 'mcp_remote':
                    continue
                package = service.store.root / resource['package_ref']
                if not package.is_relative_to(service.store.root / 'packages') or package.is_symlink():
                    raise InstallationError('resource_unsafe_path')
                before = service.installer._digest(package)
                spec = document['entries'][entry['resource_id']]
                if content_digest({'package': before, 'runtime': spec['request']['runtime'], **spec['publication']}) != resource['digest']:
                    raise InstallationError('resource_bundle_package_mismatch')
                for path in sorted(package.rglob('*')):
                    relative = path.relative_to(package)
                    relative_path(relative.as_posix())
                    count += 1
                    if count > service.installer.max_files or service.installer._protected(relative):
                        raise InstallationError('resource_bundle_limit')
                    mode = path.lstat().st_mode
                    info = tarfile.TarInfo(f"packages/{entry['resource_id']}/{relative.as_posix()}")
                    info.mode = 0o755 if mode & 0o111 else 0o644
                    if stat.S_ISDIR(mode):
                        info.type = tarfile.DIRTYPE; archive.addfile(info)
                    elif stat.S_ISLNK(mode):
                        info.type = tarfile.SYMTYPE
                        info.linkname = service.installer._safe_link(path, package)
                        archive.addfile(info)
                    elif stat.S_ISREG(mode):
                        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as reader:
                            opened = os.fstat(reader.fileno())
                            if not stat.S_ISREG(opened.st_mode):
                                raise InstallationError('resource_unsafe_path')
                            info.size = opened.st_size
                            total += info.size
                            if total > service.installer.max_bytes:
                                raise InstallationError('resource_bundle_limit')
                            archive.addfile(info, reader)
                    else:
                        raise InstallationError('resource_unsafe_path')
                if service.installer._digest(package) != before:
                    raise InstallationError('resource_bundle_package_mismatch')
        archive_path.chmod(0o600)
        service.store.permissions.require(principal, workspace, 'resources.preinstall.manage')
        os.link(archive_path, destination)
    return {'schema': 'capstone-preinstall-bundle-export/1', 'profile': profile,
            'version': document['manifest']['version'], 'package_bytes': total, 'members': count}


def _extract(service, bundle_path, root):
    maximum = limits.control_document_bytes + service.installer.max_bytes + (service.installer.max_files + 2) * 2048 + 10240
    if Path(bundle_path).stat().st_size > maximum:
        raise InstallationError('resource_bundle_limit')
    count = total = 0
    seen = set(); links = []; document = None
    with tarfile.open(bundle_path, 'r|') as archive:
        for member in archive:
            relative_path(member.name)
            if member.size < 0 or member.name in seen or set(member.pax_headers) - {'path', 'linkpath'} or member.islnk():
                raise InstallationError('resource_unsafe_path')
            seen.add(member.name)
            if member.name == 'bundle.json':
                if not member.isfile() or member.size > limits.control_document_bytes:
                    raise InstallationError('resource_bundle_metadata_limit')
                document = json.loads(archive.extractfile(member).read(limits.control_document_bytes + 1))
                continue
            parts = Path(member.name).parts
            if len(parts) < 3 or parts[0] != 'packages':
                raise InstallationError('resource_unsafe_path')
            count += 1; total += member.size
            if count > service.installer.max_files or total > service.installer.max_bytes:
                raise InstallationError('resource_bundle_limit')
            target = root / member.name
            if service.installer._protected(Path(*parts[2:])):
                raise InstallationError('resource_unsafe_path')
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.isdir():
                target.mkdir(exist_ok=True)
            elif member.issym():
                links.append((target, member.linkname))
            elif member.isfile():
                with target.open('xb') as writer:
                    reader = archive.extractfile(member)
                    while chunk := reader.read(1024 * 1024):
                        writer.write(chunk)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            else:
                raise InstallationError('resource_unsafe_path')
    for target, link in links:
        if Path(link).is_absolute():
            raise InstallationError('resource_unsafe_path')
        target.symlink_to(link)
    for target, _ in links:
        service.installer._safe_link(target, root / 'packages' / target.relative_to(root / 'packages').parts[0])
    if not isinstance(document, dict) or set(document) != {'schema', 'manifest', 'entries'} or document['schema'] != 'capstone-preinstall-bundle/1':
        raise InstallationError('resource_bundle_invalid')
    document['manifest'] = validate_manifest(document['manifest'])
    ids = {entry['resource_id'] for entry in document['manifest']['entries']}
    if not isinstance(document['entries'], dict) or set(document['entries']) != ids:
        raise InstallationError('resource_bundle_invalid')
    local_ids = {entry['resource_id'] for entry in document['manifest']['entries'] if entry['resource']['kind'] != 'mcp_remote'}
    if any(Path(name).parts[1] not in local_ids for name in seen if name != 'bundle.json'):
        raise InstallationError('resource_bundle_invalid')
    return document


def apply_bundle(service, principal, workspace, bundle_path, expected_versions):
    """Reverify every entry through the installer; acknowledge only full success."""
    store = service.store
    store.permissions.require(principal, workspace, 'resources.preinstall.manage')
    if not isinstance(expected_versions, dict):
        raise ValueError('resource_bundle_expected_versions_required')
    staging=store.root/'staging'
    staging.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='resource-bundle-',dir=staging) as temporary:
        root = Path(temporary)
        document = _extract(service, bundle_path, root)
        manifest = document['manifest']
        entries = manifest['entries']
        if set(expected_versions) - {entry['resource_id'] for entry in entries}:
            raise ValueError('resource_bundle_expected_versions_invalid')
        prepared = []
        for entry in entries:
            resource_id = entry['resource_id']
            spec = document['entries'][resource_id]
            if not isinstance(spec, dict) or set(spec) != {'request', 'publication'}:
                raise InstallationError('resource_bundle_invalid')
            request = _request(spec['request'])
            if request.kind != entry['resource']['kind'] or request.source.__dict__ != entry['resource']['source']:
                raise InstallationError('resource_bundle_source_mismatch')
            try:
                current = store.get_resource(principal, workspace, resource_id)
                actual = current['version'] if current['installed'] else None
            except KeyError:
                actual = None
            if actual != expected_versions.get(resource_id):
                raise ResourceConflict('resource_version_conflict')
            prepared.append((entry, request, spec))
        receipts = []
        for entry, request, spec in prepared:
            resource_id = entry['resource_id']
            receipt = service.installer.install_prebuilt(principal, workspace, 'bundle-' + uuid4().hex,
                resource_id, request, None if request.kind == 'mcp_remote' else root / 'packages' / resource_id,
                entry['resource'], spec['publication'], expected_versions.get(resource_id))
            receipts.append(receipt)
            if receipt['status'] != 'succeeded' or receipt['result']['version'] != entry['version']:
                return {'status': 'partial', 'receipts': receipts, 'application_receipt': None}
            result = receipt['result']
            if result['enabled'] != entry['enabled']:
                store.set_enabled(principal, workspace, resource_id, entry['enabled'], entry['version'])
        store.import_preinstall_draft(principal, workspace, manifest)
        published = store.publish_preinstall(principal, workspace, manifest['profile'])
        if published != manifest:
            raise ResourceConflict('resource_bundle_manifest_conflict')
        receipt_id = 'bundle-' + uuid4().hex
        store.record_preinstall_application(principal, workspace, manifest['profile'], manifest['version'], receipt_id)
        return {'status': 'applied', 'profile': manifest['profile'], 'version': manifest['version'],
                'application_receipt': receipt_id, 'receipts': receipts}


def main():
    """Container operator entry point; no task can select these host paths."""
    import argparse
    from .managed_resource_runtime import create_managed_resource_service
    from .native_network_policy import NativeNetworkPolicy
    from .resource_permissions import ResourcePrincipal
    parser=argparse.ArgumentParser(description='Export or verify an offline preinstall bundle.')
    parser.add_argument('operation',choices=('export','apply'))
    parser.add_argument('path',type=Path)
    parser.add_argument('--root',type=Path,default=Path('/var/lib/general-pi/managed-resources'))
    parser.add_argument('--workspace',required=True)
    parser.add_argument('--profile',default='default')
    parser.add_argument('--expected-versions',type=Path)
    args=parser.parse_args()
    if os.geteuid()!=0:parser.error('This command requires the protected executor operator.')
    # Do not mutate the running executor's firewall or infer its network state.
    # Remote acquisition is denied; local packages use their bundled bytes.
    service=create_managed_resource_service(args.root,network_policy=NativeNetworkPolicy(),environment=os.environ)
    principal=ResourcePrincipal('operator:preinstall',())
    if args.operation=='export':
        result=export_bundle(service,principal,args.workspace,args.profile,args.path)
    else:
        expected={}
        if args.expected_versions:
            with args.expected_versions.open('rb') as reader:
                raw=reader.read(limits.control_document_bytes+1)
            if len(raw)>limits.control_document_bytes:raise InstallationError('resource_declaration_limit')
            expected=json.loads(raw)
        result=apply_bundle(service,principal,args.workspace,args.path,expected)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
