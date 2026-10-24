"""Protected executor staging. Only trusted control transport calls this store."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import re
import os
import shutil
import time
from threading import RLock

from .resource_manifest import checked_resource
from .application_capacity import limits

CHUNK_BYTES = 4 * 1024**2


class NativeResourceStaging:
    def __init__(self, root: Path, *, max_file_bytes=None,
                 max_storage_bytes=None, retention_seconds=None):
        max_file_bytes = limits.upload_file_bytes if max_file_bytes is None else max_file_bytes
        max_storage_bytes = limits.input_staging_bytes if max_storage_bytes is None else max_storage_bytes
        retention_seconds = limits.retention_seconds if retention_seconds is None else retention_seconds
        if min(max_file_bytes, max_storage_bytes, retention_seconds) <= 0:
            raise ValueError('invalid staging limits')
        self.root, self.max_file_bytes = root, max_file_bytes
        self.max_storage_bytes, self.retention_seconds = max_storage_bytes, retention_seconds
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        self.lock = RLock()

    def _task(self, task_id):
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', task_id):
            raise ValueError('invalid task identity')
        return self.root / task_id

    def _directory(self, task_id, resource):
        if resource['size_bytes'] > self.max_file_bytes:
            raise ValueError('resource exceeds staging capacity')
        return self._task(task_id) / resource['resource_id']

    def remove(self, task_id):
        with self.lock:
            shutil.rmtree(self._task(task_id), ignore_errors=True)

    def sweep(self, active):
        with self.lock:
            for task in self.root.iterdir():
                if task.is_dir() and task.name not in active and time.time() - task.stat().st_mtime > self.retention_seconds:
                    self.remove(task.name)

    def control(self, value):
        if not isinstance(value, dict) or set(value) - {'task_id', 'resource', 'operation', 'index', 'content_base64'}:
            raise ValueError('invalid staging request')
        resource = checked_resource(value['resource'])
        directory = self._directory(value['task_id'], resource)
        with self.lock:
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            manifest = directory / 'manifest.json'
            if manifest.exists():
                if json.loads(manifest.read_text()) != resource:
                    raise ValueError('resource identity changed')
            else:
                # Reserve staging, assembly and the immutable execution copy.
                reserved = sum(json.loads(path.read_text())['size_bytes'] * 3
                               for path in self.root.glob('*/*/manifest.json'))
                required = resource['size_bytes'] * 3
                if reserved + required > self.max_storage_bytes or required > shutil.disk_usage(self.root).free:
                    raise ValueError('resource staging capacity reached')
                temporary = directory / 'manifest.tmp'
                temporary.write_text(json.dumps(resource, sort_keys=True))
                temporary.replace(manifest)
            os.utime(directory.parent, None)
            count = (resource['size_bytes'] + limits.upload_chunk_bytes - 1) // limits.upload_chunk_bytes
            ready = directory / 'ready'
            received = list(range(count)) if ready.exists() else sorted(int(p.stem) for p in directory.glob('*.part'))
            operation = value['operation']
            if operation == 'status':
                return {'resource_id': resource['resource_id'], 'chunk_bytes': limits.upload_chunk_bytes, 'received_parts': received}
            if operation == 'part':
                index = value['index']
                if type(index) is not int or not 0 <= index < count:
                    raise ValueError('invalid staging part')
                data = base64.b64decode(value['content_base64'], validate=True)
                if len(data) != min(limits.upload_chunk_bytes, resource['size_bytes'] - index * limits.upload_chunk_bytes):
                    raise ValueError('invalid staging byte count')
                target = directory / f'{index}.part'
                if ready.exists():
                    with (directory / 'content').open('rb') as source:
                        source.seek(index * limits.upload_chunk_bytes)
                        existing = source.read(len(data))
                    if existing != data:
                        raise ValueError('staging part changed')
                elif target.exists():
                    if target.read_bytes() != data:
                        raise ValueError('staging part changed')
                else:
                    temporary = directory / f'{index}.tmp'
                    temporary.write_bytes(data)
                    temporary.replace(target)
                return {'index': index, 'sha256': sha256(data).hexdigest(), 'size_bytes': len(data)}
            if operation != 'complete':
                raise ValueError('invalid staging operation')
            if not ready.exists():
                if received != list(range(count)):
                    raise ValueError('resource staging is incomplete')
                digest = sha256()
                temporary = directory / 'content.tmp'
                with temporary.open('wb') as target:
                    for index in range(count):
                        data = (directory / f'{index}.part').read_bytes()
                        digest.update(data)
                        target.write(data)
                if digest.hexdigest() != resource['sha256']:
                    temporary.unlink()
                    raise ValueError('resource digest mismatch')
                temporary.replace(directory / 'content')
                ready.write_text(resource['sha256'])
                for part in directory.glob('*.part'):
                    part.unlink()
            return {'resource_id': resource['resource_id'], 'sha256': resource['sha256'], 'size_bytes': resource['size_bytes']}

    def source(self, task_id, value):
        resource = checked_resource(value)
        directory = self._directory(task_id, resource)
        with self.lock:
            if (not (directory / 'ready').is_file()
                    or json.loads((directory / 'manifest.json').read_text()) != resource
                    or (directory / 'content').stat().st_size != resource['size_bytes']):
                raise ValueError('resource staging is unavailable')
            return directory / 'content'
