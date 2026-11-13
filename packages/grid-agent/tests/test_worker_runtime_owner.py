"""Worker preparation must not initialize the retired CLI."""

import builtins
from types import SimpleNamespace

from grid_agent import worker


def test_provider_worker_prepares_without_cli_import(monkeypatch, tmp_path):
    original_import = builtins.__import__
    def guarded(name, *args, **kwargs):
        if name.startswith('grid_agent.cli'):
            raise AssertionError('Worker imported CLI: ' + name)
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', guarded)
    monkeypatch.setattr(worker, 'ROOT', tmp_path)
    (tmp_path / '.env').write_text('GRID_AGENT_LLM_MODEL=file-model\n')
    monkeypatch.setenv('GRID_AGENT_LLM_MODEL', 'process-model')
    captured = {}
    application = SimpleNamespace(prepared_application=None)
    def build(*args, **kwargs):
        captured.update(kwargs)
        return application
    monkeypatch.setattr(worker, 'build_generic_application', build)
    monkeypatch.setattr(worker.ProviderCatalog, 'load', lambda path: object())
    prepared = worker._prepare({'application_id': worker.APPLICATION_ID,
        'run_id': 'owner-check', 'mode': 'provider'}, lambda event: None)
    assert prepared is not None
    assert captured['environment']['CAPABILITY_AGENT_LLM_MODEL'] == 'process-model'
    assert callable(application.completion_projector)
