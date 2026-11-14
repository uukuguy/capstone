from hashlib import sha256
import pytest
from capstone_agent.product_index_process import parse_isolated
from test_product_block_identity import selection


def run(content=b'paragraph\n', **overrides):
    parent = {**selection()['parent_ref'], 'digest':sha256(content).hexdigest()}
    budgets = dict(max_input_bytes=1024, max_blocks=10, max_output_bytes=8192,
                   wall_seconds=10, cpu_seconds=5, max_rss_bytes=512*1024*1024)
    return parse_isolated(parent, content, **{**budgets, **overrides})


def test_real_child_returns_exact_paragraph_index():
    result = run()
    assert len(result['blocks']) == 1
    assert result['blocks'][0]['content_digest'] == sha256(b'paragraph\n').hexdigest()


def test_wall_deadline_stops_real_child():
    with pytest.raises(ValueError, match='deadline'):
        run(wall_seconds=0.001)


def test_output_budget_stops_publication():
    with pytest.raises(ValueError):
        run(max_output_bytes=10)


def test_invalid_budgets_reject_before_spawn():
    with pytest.raises(ValueError, match='budget'):
        run(max_rss_bytes=0)


def test_rss_supervision_stops_child_over_budget():
    with pytest.raises(ValueError, match='memory budget'):
        run(max_rss_bytes=1)
