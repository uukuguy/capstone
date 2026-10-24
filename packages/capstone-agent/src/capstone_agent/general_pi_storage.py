"""Bounded private Pi receipts and products, with durable replay tombstones."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
from threading import RLock
import time
from .application_capacity import limits, require_capacity, CapacityExceeded


class ArtifactPersistenceError(OSError):
    """A failed save carries only products whose bytes were verified and saved."""
    def __init__(self, saved_artifacts):
        self.saved_artifacts = json.loads(json.dumps(saved_artifacts))
        super().__init__('General Pi work product persistence failed')


def request_hash(document: dict) -> str:
    return sha256(json.dumps(document, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class GeneralPiStorage:
    def __init__(self, root: Path, *, retention_seconds: float | None = None,
                 max_receipts: int | None = None, max_bytes: int | None = None):
        retention_seconds = limits.retention_seconds if retention_seconds is None else retention_seconds
        max_receipts = limits.receipt_count if max_receipts is None else max_receipts
        max_bytes = limits.native_storage_bytes if max_bytes is None else max_bytes
        if not math.isfinite(retention_seconds) or retention_seconds <= 0 or max_receipts < 1 or max_bytes < 1024:
            raise ValueError('General Pi storage limits are invalid')
        self.root = root
        self.retention, self.max_receipts, self.max_bytes = retention_seconds, max_receipts, max_bytes
        self.lock = RLock()
        for path in [root, *(root / name for name in ('records', 'observations', 'artifacts'))]:
            path.mkdir(parents=True, mode=0o700, exist_ok=True)
            path.chmod(0o700)
        sync_directory(root)

    def _write(self, path: Path, data: bytes) -> None:
        with self.lock:
            total = sum(item.stat().st_size for item in self.root.rglob('*') if item.is_file())
            current = path.stat().st_size if path.exists() else 0
            if total - current + len(data) > self.max_bytes:
                raise CapacityExceeded('native_storage_bytes', total - current + len(data),
                                       self.max_bytes, 'persistence')
            path.parent.mkdir(mode=0o700, exist_ok=True)
            sync_directory(path.parent.parent)
            temp = path.with_suffix('.tmp')
            with temp.open('wb') as stream:
                os.chmod(temp, 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temp.replace(path)
            sync_directory(path.parent)

    def load(self, task_id: str) -> dict | None:
        with self.lock:
            path = self.root / 'records' / (task_id + '.json')
            return json.loads(path.read_bytes()) if path.exists() else None

    def save(self, request: dict, result: dict | None):
        with self.lock:
            path = self.root / 'records' / (request['task_id'] + '.json')
            if not path.exists() and sum(1 for _ in path.parent.glob('*.json')) >= self.max_receipts:
                raise OSError('General Pi durable replay capacity reached')
            document = {'request_hash': request_hash(request), 'request': request, 'result': result}
            self._write(path, json.dumps(document, ensure_ascii=False).encode())

    def observation(self, task_id: str, source_id: str, data: bytes):
        self._write(self.root / 'observations' / task_id / (source_id + '.json'), data)

    def artifacts(self, task_id: str, workspace: Path, artifacts: list[dict]):
        saved = []
        try:
            require_capacity('artifact_count', len(artifacts), 'persistence')
            for artifact in artifacts:
                metadata = artifact['metadata']
                path = workspace / metadata['path']
                require_capacity('artifact_file_bytes', path.stat().st_size, 'persistence')
                data = path.read_bytes()
                if sha256(data).hexdigest() != metadata['sha256']:
                    raise OSError('General Pi work product verification failed')
                self._write(self.root / 'artifacts' / task_id / artifact['artifact_id'], data)
                saved.append(artifact)
        except (OSError, ValueError) as error:
            raise ArtifactPersistenceError(saved) from error

    def read_artifact(self, task_id: str, artifact_id: str) -> bytes:
        with self.lock:
            receipt = self.load(task_id)
            result = None if receipt is None else receipt.get('result')
            metadata = next((item['metadata'] for item in result['artifacts']
                             if item['artifact_id'] == artifact_id), None) if result else None
            if metadata is None:
                raise KeyError('General Pi work product is unavailable')
            data = (self.root / 'artifacts' / task_id / artifact_id).read_bytes()
            if len(data) > limits.artifact_file_bytes or sha256(data).hexdigest() != metadata['sha256']:
                raise OSError('General Pi work product verification failed')
            return data

    def artifact_file(self, task_id: str, source: Path, artifact: dict) -> None:
        """Persist a sealed file in bounded chunks without replacing other bytes."""
        import re
        import stat
        from uuid import uuid4
        identity = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,255}\Z')
        artifact_id, metadata = artifact['artifact_id'], artifact['metadata']
        digest, size = metadata['sha256'], metadata['size_bytes']
        if (not identity.fullmatch(task_id) or not identity.fullmatch(artifact_id)
                or not re.fullmatch(r'[a-f0-9]{64}', digest)
                or type(size) is not int or size < 1):
            raise ValueError('General Pi artifact identity is invalid')
        with self.lock:
            folder = self.root / 'artifacts' / task_id
            folder.mkdir(mode=0o700, exist_ok=True)
            target, temporary = folder / artifact_id, folder / ('.' + uuid4().hex)
            total = sum(item.stat().st_size for item in self.root.rglob('*') if item.is_file())
            if not target.exists() and total + size > self.max_bytes:
                raise CapacityExceeded('native_storage_bytes', total + size, self.max_bytes, 'persistence')
            try:
                fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as incoming, temporary.open('xb') as outgoing:
                    os.chmod(temporary, 0o600)
                    before = os.fstat(incoming.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_size != size:
                        raise OSError('General Pi artifact size changed')
                    actual, count = sha256(), 0
                    while chunk := incoming.read(1024 * 1024):
                        count += len(chunk)
                        if count > size: raise OSError('General Pi artifact size changed')
                        actual.update(chunk)
                        outgoing.write(chunk)
                    after = os.fstat(incoming.fileno())
                    stamp = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
                    if stamp(before) != stamp(after) or count != size or actual.hexdigest() != digest:
                        raise OSError('General Pi artifact bytes changed')
                    outgoing.flush()
                    os.fsync(outgoing.fileno())
                if target.exists():
                    actual, count = sha256(), 0
                    fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                    with os.fdopen(fd, 'rb') as existing:
                        if not stat.S_ISREG(os.fstat(existing.fileno()).st_mode):
                            raise OSError('General Pi artifact target is invalid')
                        while chunk := existing.read(1024 * 1024):
                            count += len(chunk)
                            actual.update(chunk)
                    if count != size or actual.hexdigest() != digest:
                        raise OSError('General Pi artifact identity has different bytes')
                else:
                    # Link publishes without replacing an existing identity.
                    os.link(temporary, target)
                    sync_directory(folder)
            finally:
                temporary.unlink(missing_ok=True)

    def sweep(self, active: set[str]) -> set[str]:
        """Expire contents; retain finite hash tombstones to forbid blind replay."""
        expired = set()
        with self.lock:
            now = time.time()
            for path in (self.root / 'records').glob('*.json'):
                if path.stem in active or now - path.stat().st_mtime < self.retention:
                    continue
                receipt = json.loads(path.read_bytes())
                if receipt.get('expired'):
                    continue
                # Deletion frees space before the compact record replaces full input.
                for kind in ('observations', 'artifacts'):
                    shutil.rmtree(self.root / kind / path.stem, ignore_errors=True)
                self._write(path, json.dumps({'request_hash': receipt['request_hash'],
                    'request': None, 'result': None, 'expired': True}).encode())
                expired.add(path.stem)
        return expired
