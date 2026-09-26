"""Explicit, portable hosted-service bindings without provider-specific loops."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from capstone_agent.artifacts import ArtifactService, GCSObjectStore, S3ObjectStore
from capstone_agent.ledger import Ledger


_HOST = re.compile(r"^[A-Za-z0-9.-]+$")


@dataclass(frozen=True, slots=True)
class HostSettings:
    database_url: str = field(repr=False)
    operator_token: str = field(repr=False)
    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]
    artifact_backend: str
    artifact_bucket: str
    s3_endpoint: str | None
    port: int
    bind_host: str
    runs_root: Path
    public_demo: bool
    session_idle_seconds: int
    worker_max_sessions: int


def _origin(value: str) -> bool:
    parsed = urlsplit(value)
    return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and parsed.netloc == parsed.netloc.lower()
            and parsed.path == "" and not parsed.query and not parsed.fragment
            and parsed.username is None and parsed.password is None)


def load_host_settings(environment: Mapping[str, str]) -> HostSettings:
    database_url = environment.get("DATABASE_URL", "")
    token = environment.get("CAPSTONE_OPERATOR_TOKEN", "")
    token_file = environment.get("CAPSTONE_OPERATOR_TOKEN_FILE", "")
    if token and token_file:
        raise ValueError("operator token source is ambiguous")
    if token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    hosts = frozenset(item.strip().lower() for item in
                      environment.get("CAPSTONE_ALLOWED_HOSTS", "").split(",") if item.strip())
    origins = frozenset(item.strip() for item in
                        environment.get("CAPSTONE_ALLOWED_ORIGINS", "").split(",") if item.strip())
    backend = environment.get("CAPSTONE_ARTIFACT_BACKEND", "")
    bucket = environment.get("CAPSTONE_ARTIFACT_BUCKET", "")
    endpoint = environment.get("CAPSTONE_S3_ENDPOINT") or None
    try:
        port = int(environment.get("PORT", "8766"))
    except ValueError:
        raise ValueError("PORT is invalid") from None
    bind_host = environment.get("CAPSTONE_BIND_HOST", "0.0.0.0")
    demo_setting = environment.get("CAPSTONE_PUBLIC_DEMO", "false").lower()
    if demo_setting not in {"true", "false"}:
        raise ValueError("CAPSTONE_PUBLIC_DEMO is invalid")
    try:
        session_idle_seconds = int(environment.get("CAPSTONE_SESSION_IDLE_SECONDS", "600"))
    except ValueError:
        raise ValueError("CAPSTONE_SESSION_IDLE_SECONDS is invalid") from None
    if not 60 <= session_idle_seconds <= 86400:
        raise ValueError("CAPSTONE_SESSION_IDLE_SECONDS is invalid")
    try:
        worker_max_sessions = int(environment.get("CAPSTONE_WORKER_MAX_SESSIONS", "8"))
    except ValueError:
        raise ValueError("CAPSTONE_WORKER_MAX_SESSIONS is invalid") from None
    if not 1 <= worker_max_sessions <= 64:
        raise ValueError("CAPSTONE_WORKER_MAX_SESSIONS is invalid")
    if not database_url.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL is invalid")
    if len(token) < 8:
        raise ValueError("operator token is invalid")
    if not hosts or any(not _HOST.fullmatch(host) for host in hosts):
        raise ValueError("allowed hosts are invalid")
    if not origins or any(not _origin(origin) for origin in origins):
        raise ValueError("allowed origins are invalid")
    if backend not in {"s3", "gcs"} or not bucket:
        raise ValueError("artifact storage is invalid")
    if endpoint is not None and (backend != "s3" or not _origin(endpoint)):
        raise ValueError("S3 endpoint is invalid")
    if port < 1 or port > 65535 or bind_host not in {"0.0.0.0", "127.0.0.1", "::"}:
        raise ValueError("server bind is invalid")
    default_runs = Path(__file__).resolve().parents[4] / "runs" / "capstone-agent"
    runs_root = Path(environment.get("CAPSTONE_RUNS_ROOT", str(default_runs)))
    return HostSettings(database_url, token, hosts, origins, backend, bucket,
                        endpoint, port, bind_host, runs_root, demo_setting == "true",
                        session_idle_seconds, worker_max_sessions)


def build_artifacts(settings: HostSettings, ledger: Ledger) -> ArtifactService:
    if settings.artifact_backend == "s3":
        store = S3ObjectStore(settings.artifact_bucket, endpoint_url=settings.s3_endpoint)
    else:
        store = GCSObjectStore(settings.artifact_bucket)
    return ArtifactService(ledger, store, settings.runs_root)
