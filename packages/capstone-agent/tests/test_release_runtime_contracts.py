"""Release checks for graceful empty/error-path runtime contracts."""
import pytest

from capstone_agent.domain_node_report import domain_execution_record
from capstone_agent.domain_tool_client import load_domain_tool_catalogs


def test_absent_operator_token_returns_the_complete_empty_catalog_contract():
    assert load_domain_tool_catalogs({'profiles': []}, origins={}, token='') == ({}, {}, [])


@pytest.mark.parametrize('role', [[], {}, 1, None])
def test_invalid_domain_report_role_is_not_admitted(role):
    record = domain_execution_record('family', {'role': role, 'node_text': 'observed failure'})
    assert 'role' not in record
    assert record['node_text'] == 'observed failure'
