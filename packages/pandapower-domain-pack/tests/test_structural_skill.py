from __future__ import annotations

import json
from pathlib import Path
import sys
import pytest

from pandapower_domain.execution import GridctlExecutor, sanitize_environment
from pandapower_domain.guide import PandapowerGuideProvider


def test_original_adapter_is_a_digest_bound_published_guide():
    guide = PandapowerGuideProvider().open("powerskills-pandapower-adapter")
    assert "diagnostic.structural" in guide["text"]
    assert "analysis.run" in guide["text"]
    assert "05bda3a51d5f1ecad888d4d4663c28478c643a7e" in guide["text"]
    assert "N-2" in guide["text"] and "unavailable" in guide["text"]


def test_trusted_prepared_config_crosses_actual_sanitized_launch(tmp_path):
    managed = tmp_path / "managed"
    managed.mkdir()
    install_id = "installs/" + "a" * 32
    digest = "b" * 64
    (managed / "current.json").write_text(json.dumps({"install_id": install_id, "descriptor_sha256": digest}))
    executable = tmp_path / "gridctl"
    executable.write_text(f"#!{sys.executable}\n" +
        "import os,json,sys\nr=json.loads(sys.stdin.read())\n" +
        "assert 'PROVIDER_KEY' not in os.environ\n" +
        "assert 'CAPSTONE_POWERMCP_UNTRUSTED' not in os.environ\n" +
        f"assert os.environ['CAPSTONE_POWERMCP_MANAGED_ROOT'] == {str(managed)!r}\n" +
        f"assert os.environ['CAPSTONE_POWERMCP_INSTALL_ID'] == {install_id!r}\n" +
        f"assert os.environ['CAPSTONE_POWERMCP_DESCRIPTOR_SHA256'] == {digest!r}\n" +
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0','request_id':r['request_id'],'ok':True,'result':{}}))\n")
    executable.chmod(0o755)
    executor = GridctlExecutor(executable=executable, workspace=tmp_path,
        environment={"CAPSTONE_POWERMCP_MANAGED_ROOT": str(managed), "PROVIDER_KEY": "hidden",
                     "CAPSTONE_POWERMCP_UNTRUSTED": "hidden"})
    # Acceptance freezes the installation. A later installation cannot change
    # the authority process selected by this prepared executor.
    (managed / "current.json").write_text(json.dumps({"install_id": "installs/" + "c" * 32, "descriptor_sha256": "d" * 64}))
    assert executor.invoke("analysis.operation.describe", {"operation": "diagnostic.structural"}) == {}


def test_fixed_runtime_names_do_not_admit_prefix_wildcards():
    selected = sanitize_environment({"CAPSTONE_POWERMCP_MANAGED_ROOT": "/fixed", "CAPSTONE_POWERMCP_SECRET": "secret", "OPENAI_API_KEY": "secret"})
    assert selected == {"CAPSTONE_POWERMCP_MANAGED_ROOT": "/fixed"}


@pytest.mark.parametrize("pointer", [
    {"install_id": "outside", "descriptor_sha256": "b" * 64},
    {"install_id": "installs/" + "a" * 32, "descriptor_sha256": "invalid"},
])
def test_invalid_initial_pointer_cannot_retarget_a_prepared_executor(tmp_path, pointer):
    managed = tmp_path / "managed"
    managed.mkdir()
    (managed / "current.json").write_text(json.dumps(pointer))
    executable = tmp_path / "gridctl"
    executable.write_text(f"#!{sys.executable}\n" +
        "import os,json,sys\nr=json.loads(sys.stdin.read())\n" +
        "assert os.environ.get('CAPSTONE_POWERMCP_INSTALL_ID') == 'unavailable'\n" +
        "print(json.dumps({'protocol':'grid-capability','protocol_version':'1.0','request_id':r['request_id'],'ok':True,'result':{}}))\n")
    executable.chmod(0o755)
    executor = GridctlExecutor(executable=executable, workspace=tmp_path,
        environment={"CAPSTONE_POWERMCP_MANAGED_ROOT": str(managed)})
    (managed / "current.json").write_text(json.dumps({"install_id": "installs/" + "c" * 32, "descriptor_sha256": "d" * 64}))
    assert executor.invoke("analysis.operation.describe", {"operation": "diagnostic.structural"}) == {}
