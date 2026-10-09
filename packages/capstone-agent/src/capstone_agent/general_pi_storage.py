"""Bounded private Pi receipts and products, with durable replay tombstones."""
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import shutil
from threading import RLock
import time


def request_hash(document: dict) -> str:
    return sha256(json.dumps(document, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class GeneralPiStorage:
    def __init__(self, root: Path, *, retention_seconds: float = 86400,
                 max_receipts: int = 4096, max_bytes: int = 64 * 1024 * 1024):
        if not math.isfinite(retention_seconds) or retention_seconds <= 0 or max_receipts < 1 or max_bytes < 1024:
            raise ValueError('General Pi storage limits are invalid')
        self.root = root
        self.retention, self.max_receipts, self.max_bytes = retention_seconds, max_receipts, max_bytes
        self.lock = RLock()
        for path in [root, *(root / name for name in ('records', 'observations', 'artifacts'))]:
            path.mkdir(parents=True, mode=0o700, exist_ok=True)
            path.chmod(0o700)

    def _write(self, path: Path, data: bytes) -> None:
        with self.lock:
            total = sum(item.stat().st_size for item in self.root.rglob('*') if item.is_file())
            current = path.stat().st_size if path.exists() else 0
            if total - current + len(data) > self.max_bytes:
                raise OSError('General Pi private storage quota reached')
            path.parent.mkdir(mode=0o700, exist_ok=True)
            temp = path.with_suffix('.tmp')
            with temp.open('wb') as stream:
                os.chmod(temp, 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            temp.replace(path)

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
        total = 0
        for artifact in artifacts:
            metadata = artifact['metadata']
            path = workspace / metadata['path']
            data = path.read_bytes()
            total += len(data)
            if total > 8 * 1024 * 1024 or sha256(data).hexdigest() != metadata['sha256']:
                raise OSError('General Pi work product is invalid or too large')
            self._write(self.root / 'artifacts' / task_id / artifact['artifact_id'], data)

    def read_artifact(self, task_id: str, artifact_id: str) -> bytes:
        with self.lock:
            receipt = self.load(task_id)
            result = None if receipt is None else receipt.get('result')
            metadata = next((item['metadata'] for item in result['artifacts']
                             if item['artifact_id'] == artifact_id), None) if result else None
            if metadata is None:
                raise KeyError('General Pi work product is unavailable')
            data = (self.root / 'artifacts' / task_id / artifact_id).read_bytes()
            if len(data) > 4 * 1024 * 1024 or sha256(data).hexdigest() != metadata['sha256']:
                raise OSError('General Pi work product verification failed')
            return data

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
