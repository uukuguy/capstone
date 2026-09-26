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
    assert "password" not in repr(settings)
    assert "top-secret-token" not in repr(settings)


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
    assert load_host_settings(env).public_demo is True
    env["CAPSTONE_PUBLIC_DEMO"] = "maybe"
    with pytest.raises(ValueError):
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
