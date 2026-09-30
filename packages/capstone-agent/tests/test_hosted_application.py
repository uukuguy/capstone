from __future__ import annotations

import ast
from pathlib import Path

import pytest

from capstone_agent import hosted
from capstone_agent.harness import PiPromptSession
from capstone_agent.thread_application import ThreadApplicationAssembly


def _assembly() -> ThreadApplicationAssembly:
    class Session:
        def start(self) -> None: pass
        def prompt_and_wait(self, question, *, on_semantic_event, correlation_id, on_heartbeat):
            return "answer"
        def stop(self) -> None: pass

    return ThreadApplicationAssembly.from_authority(
        default_model_id="model",
        model_resolver=lambda model_id: {
            "model_id": model_id,
            "revision_ref": "revision:sha256:" + "a" * 64,
            "implementation_family": "test",
        },
        session_factory=lambda _claim: Session(),
    )


@pytest.mark.parametrize(
    ("runner", "expected_mode"),
    ((hosted.run_hosted_api, "serve-hosted"), (hosted.run_hosted_worker, "work-hosted")),
)
def test_hosted_runner_builds_once_and_dispatches_exact_mode(
    monkeypatch: pytest.MonkeyPatch,
    runner,
    expected_mode: str,
) -> None:
    assembly = _assembly()
    built = []
    calls = []

    def factory() -> ThreadApplicationAssembly:
        built.append(True)
        return assembly

    def fake_main(argv, *, thread_application):
        calls.append((argv, thread_application))
        return 23

    monkeypatch.setattr(hosted, "capstone_main", fake_main)

    assert runner(factory) == 23
    assert built == [True]
    assert calls == [([expected_mode], assembly)]


def test_hosted_runner_rejects_an_invalid_factory_result() -> None:
    def invalid_factory() -> ThreadApplicationAssembly:
        return object()  # type: ignore[return-value]

    with pytest.raises(TypeError, match="ThreadApplicationAssembly"):
        hosted.run_hosted_api(invalid_factory)


def test_capstone_hosted_module_has_no_domain_imports() -> None:
    source_path = Path(hosted.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    assert all(
        not name.startswith(("grid_agent", "grid_simulator", "pandapower", "pypsa"))
        for name in imported
    )
