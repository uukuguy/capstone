"""The formal application profile must not require the retired CLI package."""

import subprocess
import sys


def test_application_profile_loads_with_grid_agent_imports_blocked():
    code = '''
import importlib.abc
import sys
class NoLegacyApplication(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "grid_agent" or fullname.startswith("grid_agent."):
            raise AssertionError("Application still depends on legacy package: " + fullname)
sys.meta_path.insert(0, NoLegacyApplication())
from pandapower_application.profile import build_pandapower_application_profile
from pandapower_application.worker import _prepare
from pandapower_application.case_preview import open_case_diagram
assert open_case_diagram.__module__ == 'pandapower_application.case_preview'
assert _prepare.__module__ == 'pandapower_application.worker'
from pandapower_application.scripted_execution import execute_application_case
assert execute_application_case.__module__ == 'pandapower_application.scripted_execution'
from pandapower_application.composition import _runtime_host_dependencies
assert all(not item.__module__.startswith('grid_agent') for item in _runtime_host_dependencies())
from pandapower_application.registry import build_trusted_application_registry
from pandapower_application.thread_capabilities import PANDAPOWER_PROFILE_DESCRIPTOR
assert build_trusted_application_registry().resolve("pandapower-static-analysis").manifest.application_id == "pandapower-static-analysis"
assert PANDAPOWER_PROFILE_DESCRIPTOR is not None
profile = build_pandapower_application_profile()
assert profile.manifest.application_id == "pandapower-static-analysis"
assert profile.report_shell.__class__.__module__ == "pandapower_application.report_shell"
assert profile.domains[0].profile.missing_application_components() == ()
assert profile.domains[0].sharing_policy.mode == "deny"
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
