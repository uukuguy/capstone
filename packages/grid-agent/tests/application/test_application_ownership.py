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
profile = build_pandapower_application_profile()
assert profile.manifest.application_id == "pandapower-static-analysis"
assert profile.report_shell.__class__.__module__ == "pandapower_application.report_shell"
assert profile.domains[0].profile.missing_application_components() == ()
assert profile.domains[0].sharing_policy.mode == "deny"
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
