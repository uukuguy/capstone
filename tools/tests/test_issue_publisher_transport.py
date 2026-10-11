import io
import json
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from tools.issue_automation.github import GitHub


def test_publisher_uses_bearer_auth_without_credential_subprocess(monkeypatch):
    github = GitHub(SimpleNamespace(repository="uukuguy/capstone", publisher_jwt_env="CAPSTONE_TEST_JWT"), root=".")
    monkeypatch.setattr(github, "_jwt", lambda: "test-jwt")
    requests = []

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert timeout == 60
            return io.BytesIO(b'{"id": 123}')

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: Opener())
    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: pytest.fail("publisher credential entered a subprocess"))
    assert github._publisher_api("GET", "app") == {"id": 123}
    request = requests[0]
    assert request.full_url == "https://api.github.com/app"
    assert request.get_header("Authorization") == "Bearer test-jwt"


def test_installation_request_uses_installation_token_and_json_body(monkeypatch):
    github = GitHub(SimpleNamespace(repository="uukuguy/capstone", publisher_jwt_env="CAPSTONE_TEST_JWT"), root=".")
    github.installation_token = "test-installation-token"
    monkeypatch.setattr(github, "_jwt", lambda: pytest.fail("installation request must not use App JWT"))

    class Opener:
        def open(self, request, timeout):
            assert request.get_header("Authorization") == "Bearer test-installation-token"
            assert json.loads(request.data) == {"title": "中文标题"}
            return io.BytesIO(b'{"number": 1}')

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: Opener())
    assert github._publisher_api("POST", "repos/uukuguy/capstone/issues", {"title": "中文标题"}) == {"number": 1}


def test_publisher_rejects_redirect_and_does_not_expose_response_or_token(monkeypatch):
    github = GitHub(SimpleNamespace(repository="uukuguy/capstone", publisher_jwt_env="CAPSTONE_TEST_JWT"), root=".")
    monkeypatch.setattr(github, "_jwt", lambda: "test-jwt")

    def opener(*handlers):
        assert handlers[0].redirect_request(None, None, None, None, None, None) is None
        class Opener:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 302, "secret-response", {}, None)
        return Opener()

    monkeypatch.setattr("urllib.request.build_opener", opener)
    with pytest.raises(RuntimeError, match="HTTP 302") as error:
        github._publisher_api("GET", "app")
    assert "secret-response" not in str(error.value)
    assert "test-jwt" not in str(error.value)


def test_invalid_credential_is_rejected_without_disclosing_it(monkeypatch):
    github = GitHub(SimpleNamespace(repository="uukuguy/capstone"), root=".")
    monkeypatch.setattr(github, "_jwt", lambda: "private-test-token\ninvalid")
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: pytest.fail("invalid credential reached transport"))
    with pytest.raises(ValueError) as error:
        github._publisher_api("GET", "app")
    assert "private-test-token" not in str(error.value)


def test_cli_does_not_print_invalid_publisher_credential(monkeypatch, capsys):
    from tools.issue_automation import cli

    github = GitHub(SimpleNamespace(repository="uukuguy/capstone"), root=".")
    monkeypatch.setattr(github, "_jwt", lambda: "private-test-token\ninvalid")
    monkeypatch.setattr(cli, "execute", lambda args: github._publisher_api("GET", "app"))
    assert cli.main(["doctor"]) == 2
    output = capsys.readouterr()
    assert "private-test-token" not in output.out + output.err
    assert json.loads(output.err)["error"] == "GitHub publisher credential format is invalid"
