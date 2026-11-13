import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def load_entry():
    path = Path(__file__).resolve().parents[1] / "install_local_pi.py"
    spec = importlib.util.spec_from_file_location("install_local_pi", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("invalid", [None, "marker", "version"])
def test_reuse_requires_managed_identity_and_matching_version(monkeypatch, tmp_path, invalid):
    entry = load_entry()
    calls = []
    command = SimpleNamespace(path=tmp_path / "pi.js")
    monkeypatch.setattr(entry.PiRuntimeLock, "load", lambda path: object())

    class Locator:
        def __init__(self, *args, **kwargs):
            pass

        def resolve(self, *, require_managed):
            assert require_managed
            calls.append("identity")
            if invalid == "marker":
                raise entry.PiRuntimeLocatorError("invalid marker")
            return command

        def probe(self):
            calls.append("version")
            if invalid == "version":
                raise entry.PiRuntimeLocatorError("wrong version")
            return command

    class Installer:
        def __init__(self, *args):
            pass

        def install(self):
            calls.append("install")
            return command

    monkeypatch.setattr(entry, "PiRuntimeLocator", Locator)
    monkeypatch.setattr(entry, "PiRuntimeInstaller", Installer)
    assert entry.ensure_local_pi(tmp_path) == command.path
    assert ("install" in calls) == (invalid is not None)
