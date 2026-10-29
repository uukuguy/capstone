from urllib.parse import quote

import pytest

from capstone_agent.workspace_scope import workspace_name, workspace_header


def test_workspace_header_defaults_and_decodes_chinese_once():
    assert workspace_header(None) == 'enterprise'
    assert workspace_header(quote(' 电网研究 ')) == '电网研究'
    assert workspace_header(quote('a%20b')) == 'a%20b'
    assert workspace_name('e\u0301') == 'é'


@pytest.mark.parametrize('value', ['', ' ', 'x'*129, 'x\n', 'a\x7fb', 'a\u0085b', 'a\u202eb', '\ud800'])
def test_workspace_name_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        workspace_name(value)


@pytest.mark.parametrize('value', ['', '%', '%Q0', '%FF', '%C0%AF', '%00', 'x'*1537])
def test_workspace_header_rejects_invalid_encoding(value):
    with pytest.raises(ValueError):
        workspace_header(value)
