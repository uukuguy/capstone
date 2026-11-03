import importlib.util
import json
from pathlib import Path


def test_policy_initialization_does_not_reset_revocation(tmp_path):
    source=Path(__file__).parents[3]/'deploy/prepare_resource_policy.py'
    spec=importlib.util.spec_from_file_location('prepare_resource_policy',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    template=tmp_path/'template.json';template.write_text('{"version":1,"profiles":{}}')
    target=module.prepare(tmp_path/'private',template)
    assert json.loads(target.read_text())['version']==1
    target.write_text('{"version":1,"profiles":{"local":{"rules":[]}}}')
    module.prepare(tmp_path/'private',template)
    assert json.loads(target.read_text())['profiles']['local']['rules']==[]
