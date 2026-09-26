"""Bounded private artifacts for current-run reports and evidence projections."""

from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path
from typing import Protocol

from capstone_agent.ledger import ArtifactRecord, Ledger


MAX_ARTIFACT_BYTES = 2_000_000


class ObjectStore(Protocol):
    def put(self, key: str, content: bytes, mime: str) -> None: ...

    def get(self, key: str, limit: int) -> bytes: ...


class MemoryObjectStore:
    """Small deterministic test adapter; production uses S3 or GCS."""

    def __init__(self) -> None:
        self.contents: dict[str, bytes] = {}

    def put(self, key: str, content: bytes, mime: str) -> None:
        self.contents[key] = content

    def get(self, key: str, limit: int) -> bytes:
        return self.contents[key][:limit + 1]


class S3ObjectStore:
    """Private S3-compatible adapter for local and Railway buckets."""

    def __init__(self, bucket: str, *, endpoint_url: str | None = None,
                 region_name: str | None = None) -> None:
        if not bucket:
            raise ValueError("artifact bucket is required")
        import boto3

        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=endpoint_url,
                                   region_name=region_name)

    def put(self, key: str, content: bytes, mime: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content,
                               ContentType=mime)

    def get(self, key: str, limit: int) -> bytes:
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        try:
            return body.read(limit + 1)
        finally:
            body.close()


class GCSObjectStore:
    """Private Google Cloud Storage adapter for Cloud Run."""

    def __init__(self, bucket: str) -> None:
        if not bucket:
            raise ValueError("artifact bucket is required")
        from google.cloud import storage

        self.bucket = storage.Client().bucket(bucket)

    def put(self, key: str, content: bytes, mime: str) -> None:
        self.bucket.blob(key).upload_from_string(
            content, content_type=mime, if_generation_match=0,
        )

    def get(self, key: str, limit: int) -> bytes:
        return self.bucket.blob(key).download_as_bytes(start=0, end=limit)


class ArtifactService:
    def __init__(self, ledger: Ledger, store: ObjectStore, runs_root: Path) -> None:
        self.ledger = ledger
        self.store = store
        self.runs_root = runs_root.resolve()

    def _save(self, session_id: str, kind: str, ref: str | None,
              content: bytes, mime: str) -> None:
        if len(content) > MAX_ARTIFACT_BYTES:
            raise ValueError("artifact exceeds size limit")
        session = self.ledger.get_session(session_id)
        if session is None or session.run_id is None:
            raise ValueError("current run is unavailable")
        key = "objects/" + secrets.token_hex(24)
        digest = hashlib.sha256(content).hexdigest()
        self.store.put(key, content, mime)
        self.ledger.save_artifact(ArtifactRecord(
            session_id, session.run_id, kind, ref, key, digest, mime, len(content),
        ))

    def _read(self, session_id: str, kind: str, ref: str | None) -> bytes | None:
        record = self.ledger.get_artifact(session_id, kind, ref)
        if record is None:
            return None
        content = self.store.get(record.object_key, MAX_ARTIFACT_BYTES)
        if (len(content) != record.byte_count
                or hashlib.sha256(content).hexdigest() != record.sha256):
            raise ValueError("artifact integrity check failed")
        return content

    def save_evidence(self, session_id: str, ref: str, projection: object) -> None:
        if not ref or len(ref) > 2048:
            raise ValueError("evidence reference is invalid")
        content = json.dumps(projection, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
        self._save(session_id, "evidence", ref, content, "application/json")

    def read_evidence(self, session_id: str, ref: str) -> object | None:
        content = self._read(session_id, "evidence", ref)
        return json.loads(content) if content is not None else None

    def save_report(self, session_id: str, path: Path) -> None:
        session = self.ledger.get_session(session_id)
        if session is None or session.run_id is None:
            raise ValueError("current run is unavailable")
        resolved = path.resolve()
        run_dir = (self.runs_root / session.run_id).resolve()
        if not resolved.is_relative_to(run_dir) or not resolved.is_file():
            raise ValueError("report is outside current run")
        with resolved.open("rb") as stream:
            content = stream.read(MAX_ARTIFACT_BYTES + 1)
        self._save(session_id, "report", None, content, "text/markdown; charset=utf-8")

    def read_report(self, session_id: str) -> str | None:
        content = self._read(session_id, "report", None)
        return content.decode("utf-8") if content is not None else None
