from __future__ import annotations

import pytest

from capstone_agent.hosting import load_host_settings


def _env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql://operator:password@db/capstone",
        "CAPSTONE_OPERATOR_TOKEN": "top-secret-token",
        "CAPSTONE_ALLOWED_HOSTS": "localhost,capstone.example.com",
        "CAPSTONE_ALLOWED_ORIGINS": "http://localhost:5173,https://app.example.com",
        "CAPSTONE_ARTIFACT_BACKEND": "s3",
        "CAPSTONE_ARTIFACT_BUCKET": "capstone-private",
        "CAPSTONE_S3_ENDPOINT": "http://objects:9000",
        "PORT": "8080",
    }


def test_host_settings_require_explicit_cross_platform_bindings() -> None:
    settings = load_host_settings(_env())
    assert settings.port == 8080
    assert settings.allowed_hosts == {"localhost", "capstone.example.com"}
    assert settings.allowed_origins == {
        "http://localhost:5173", "https://app.example.com",
    }
    assert settings.session_idle_seconds == 600
    assert settings.worker_max_sessions == 8
    assert settings.worker_wake_url is None
    assert "password" not in repr(settings)
    assert "top-secret-token" not in repr(settings)


def test_host_settings_validate_configurable_session_idle_timeout() -> None:
    env = _env()
    env["CAPSTONE_SESSION_IDLE_SECONDS"] = "900"
    assert load_host_settings(env).session_idle_seconds == 900
    for invalid in ("0", "59", "not-a-number"):
        env["CAPSTONE_SESSION_IDLE_SECONDS"] = invalid
        with pytest.raises(ValueError, match="CAPSTONE_SESSION_IDLE_SECONDS"):
            load_host_settings(env)


def test_host_settings_validate_worker_capacity() -> None:
    env = _env()
    env["CAPSTONE_WORKER_MAX_SESSIONS"] = "12"
    assert load_host_settings(env).worker_max_sessions == 12
    for invalid in ("0", "65", "not-a-number"):
        env["CAPSTONE_WORKER_MAX_SESSIONS"] = invalid
        with pytest.raises(ValueError, match="CAPSTONE_WORKER_MAX_SESSIONS"):
            load_host_settings(env)


def test_host_settings_accept_operator_secret_file(tmp_path) -> None:
    secret = tmp_path / "operator.token"
    secret.write_text("file-secret-token\n", encoding="utf-8")
    env = _env()
    del env["CAPSTONE_OPERATOR_TOKEN"]
    env["CAPSTONE_OPERATOR_TOKEN_FILE"] = str(secret)
    assert load_host_settings(env).operator_token == "file-secret-token"
    env["CAPSTONE_OPERATOR_TOKEN"] = "another-secret-token"
    with pytest.raises(ValueError):
        load_host_settings(env)


def test_host_settings_enable_public_demo_explicitly() -> None:
    assert load_host_settings(_env()).public_demo is False
    env = _env()
    env["CAPSTONE_PUBLIC_DEMO"] = "true"
    env["CAPSTONE_PUBLIC_PROVIDER"] = "deepseek"
    env["CAPSTONE_PUBLIC_MODEL"] = "deepseek-v4-pro"
    assert load_host_settings(env).public_demo is True
    assert load_host_settings(env).public_provider == "deepseek"
    assert load_host_settings(env).public_model == "deepseek-v4-pro"
    env["CAPSTONE_PUBLIC_DEMO"] = "maybe"
    with pytest.raises(ValueError):
        load_host_settings(env)


def test_host_settings_validate_private_worker_wake_url() -> None:
    env = _env()
    env["CAPSTONE_WORKER_WAKE_URL"] = "http://worker:8766"
    assert load_host_settings(env).worker_wake_url == "http://worker:8766"
    for invalid in ("https://worker/wake", "http://user:pass@worker:8766",
                    "http://worker:8766/wake", "http://worker:8766?x=1"):
        env["CAPSTONE_WORKER_WAKE_URL"] = invalid
        with pytest.raises(ValueError, match="CAPSTONE_WORKER_WAKE_URL"):
            load_host_settings(env)


@pytest.mark.parametrize("name,value", [
    ("DATABASE_URL", ""),
    ("CAPSTONE_OPERATOR_TOKEN", "short"),
    ("CAPSTONE_ALLOWED_HOSTS", "https://app.example.com"),
    ("CAPSTONE_ALLOWED_ORIGINS", "https://app.example.com/path"),
    ("CAPSTONE_ARTIFACT_BACKEND", "filesystem"),
    ("CAPSTONE_ARTIFACT_BUCKET", ""),
    ("PORT", "0"),
])
def test_host_settings_reject_incomplete_or_unsafe_values(name: str, value: str) -> None:
    env = _env()
    env[name] = value
    with pytest.raises(ValueError):
        load_host_settings(env)
