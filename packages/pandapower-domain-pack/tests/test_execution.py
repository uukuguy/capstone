from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pandapower_domain.execution import (
    GridctlClientError,
    GridctlExecutor,
    SimulatorCapabilityError,
    SimulatorOperationError,
    sanitize_environment,
)


def _write_executable(path: Path, source: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{source}", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_executor_uses_json_stdin_and_clean_stdout(
    tmp_path: Path, clean_child_environment: None
) -> None:
    executable = _write_executable(
        tmp_path / "gridctl",
        "import json,sys\n"
        "request=json.loads(sys.stdin.read())\n"
        "assert request['capability'] == 'environment.describe'\n"
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0',"
        "'request_id':request['request_id'],'ok':True,'result':{'executable_capabilities':[{'id':'context.open'}]}},separators=(',',':')))\n"
        "print('diagnostic', file=sys.stderr)\n",
    )
    executor = GridctlExecutor(executable=executable, workspace=tmp_path, timeout_seconds=5)

    result = executor.invoke("environment.describe", {})

    assert result["executable_capabilities"]
    assert executor.last_diagnostics == "diagnostic\n"


def test_executor_preserves_exact_request_shape(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    executable = _write_executable(
        tmp_path / "gridctl",
        "import json, pathlib, sys\n"
        f"request_path=pathlib.Path({str(request_path)!r})\n"
        "request=json.loads(sys.stdin.read())\n"
        "request_path.write_text(json.dumps(request,sort_keys=True),encoding='utf-8')\n"
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0',"
        "'request_id':request['request_id'],'ok':True,'result':{'models':[{'model_id':'ieee39'}]}},separators=(',',':')))\n",
    )

    result = GridctlExecutor(executable=executable, workspace=tmp_path).invoke(
        "model.list", {}
    )

    request = json.loads(request_path.read_text(encoding="utf-8"))
    assert result["models"] == [{"model_id": "ieee39"}]
    assert request["protocol"] == "grid-capability"
    assert request["protocol_version"] == "1.0"
    assert request["capability"] == "model.list"
    assert request["arguments"] == {}
    assert "operation" not in request


def test_executor_filters_secret_environment_values(tmp_path: Path) -> None:
    environment_path = tmp_path / "environment.json"
    executable = _write_executable(
        tmp_path / "gridctl",
        "import json, os, pathlib\n"
        f"pathlib.Path({str(environment_path)!r}).write_text(json.dumps(dict(os.environ)), encoding='utf-8')\n"
        "request=json.loads(input())\n"
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0',"
        "'request_id':request['request_id'],'ok':True,'result':{}}))\n",
    )

    GridctlExecutor(executable=executable, workspace=tmp_path).invoke("model.list", {})

    child_environment = json.loads(environment_path.read_text(encoding="utf-8"))
    assert "GRID_AGENT_SECRET" not in child_environment


def test_sanitize_environment_allows_only_runtime_names() -> None:
    runtime_environment = {
        "__CF_USER_TEXT_ENCODING": "0x1F5:0x19:0x34",
        "PATH": "/usr/bin",
        "LANG": "C.UTF-8",
        "LANGUAGE": "en_US",
        "LC_ALL": "C.UTF-8",
        "TZ": "UTC",
        "TMPDIR": "/tmp",
        "TEMP": "/tmp",
        "TMP": "/tmp",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONHASHSEED": "123",
        "SYSTEMROOT": "C:\\Windows",
        "WINDIR": "C:\\Windows",
        "PATHEXT": ".COM;.EXE",
    }
    ambient_environment = {
        "AWS_ACCESS_KEY_ID": "aws-secret",
        "ALIYUN_ACCESS_KEY_ID": "aliyun-secret",
        "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/google.json",
        "OPENAI_API_KEY": "openai-secret",
        "APIKEY": "api-secret",
        "SERVICE_SECRETKEY": "secret-key",
        "PASSPHRASE": "passphrase",
        "CUSTOM_BUSINESS_FLAG": "business-value",
        "APP_MODE": "validation",
        "PYTHONPATH": "/tmp/provider-code",
        "HOME": "/Users/operator",
        "HTTP_PROXY": "http://proxy.example",
    }

    assert sanitize_environment({**runtime_environment, **ambient_environment}) == runtime_environment


def test_executor_preserves_typed_capability_error(tmp_path: Path) -> None:
    executable = _write_executable(
        tmp_path / "gridctl",
        "import json,sys\n"
        "request=json.loads(sys.stdin.read())\n"
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0',"
        "'request_id':request['request_id'],'ok':False,'error':{'code':'invalid_arguments','phase':'validate','message':'bad input','retryable':False,'state_effect':'none','allowed_recovery_actions':['correct_arguments'],'evidence_refs':['evidence:sha256:'+'1'*64],'details':{'field':'context_ref'}}},separators=(',',':')))\n",
    )

    with pytest.raises(SimulatorCapabilityError) as raised:
        GridctlExecutor(executable=executable, workspace=tmp_path).invoke(
            "context.open", {"unexpected": True}
        )

    assert raised.value.error["code"] == "invalid_arguments"
    assert raised.value.error["details"] == {"field": "context_ref"}


@pytest.mark.parametrize(
    "response",
    [
        {"protocol": "wrong", "protocol_version": "1.0"},
        {"protocol": "grid-capability", "protocol_version": "9.9"},
    ],
)
def test_executor_rejects_uncorrelated_protocol_response(
    tmp_path: Path, response: dict[str, object]
) -> None:
    executable = _write_executable(
        tmp_path / "gridctl",
        "import json,sys\n"
        f"response={response!r}\n"
        "request=json.loads(sys.stdin.read())\n"
        "response['request_id']=request['request_id']\n"
        "response['ok']=True\n"
        "response['result']={}\n"
        "print(json.dumps(response))\n",
    )

    with pytest.raises(GridctlClientError, match="does not match"):
        GridctlExecutor(executable=executable, workspace=tmp_path).invoke(
            "model.list", {}
        )


def test_executor_maps_non_capability_failure_to_typed_operation_error(
    tmp_path: Path,
) -> None:
    executable = _write_executable(
        tmp_path / "gridctl",
        "import json,sys\n"
        "request=json.loads(sys.stdin.read())\n"
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0',"
        "'request_id':request['request_id'],'ok':False,'error':'failed'},separators=(',',':')))\n",
    )

    with pytest.raises(SimulatorOperationError, match="operation failed"):
        GridctlExecutor(executable=executable, workspace=tmp_path).invoke(
            "model.list", {}
        )


def test_executor_maps_timeout_to_transport_error(tmp_path: Path) -> None:
    executable = _write_executable(
        tmp_path / "gridctl",
        "import time\n"
        "time.sleep(1)\n",
    )

    with pytest.raises(GridctlClientError, match="could not complete"):
        GridctlExecutor(
            executable=executable, workspace=tmp_path, timeout_seconds=0.01
        ).invoke("model.list", {})
