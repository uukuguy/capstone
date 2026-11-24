"""Advisory checks over admitted table projections, without changing their data."""

from collections.abc import Mapping
from functools import lru_cache

from .harness_validation import Decision, RuleBundle, load_rule_bundle, published_rule_bundle_bytes


def _row_coverage(table: Mapping[str, object]) -> Decision[Mapping[str, object]]:
    rows, page = table.get("rows"), table.get("pagination")
    if isinstance(rows, list) and isinstance(page, Mapping):
        total = page.get("total_rows")
        if type(total) is int and total < len(rows):
            return Decision.rejected(table, "table_row_count_exceeds_declared_coverage")
    return Decision.accepted(table)


def _unit_labels(table: Mapping[str, object]) -> Decision[Mapping[str, object]]:
    columns = table.get("columns")
    if isinstance(columns, list):
        for column in columns:
            if isinstance(column, Mapping) and isinstance(unit := column.get("unit"), str) and not unit.strip():
                return Decision.rejected(table, "table_unit_label_blank")
    return Decision.accepted(table)


@lru_cache(maxsize=1)
def result_table_rule_bundle() -> RuleBundle[Mapping[str, object]]:
    return load_rule_bundle(published_rule_bundle_bytes(), {
        "table_row_coverage": _row_coverage,
        "table_unit_labels": _unit_labels,
    }, target="result.table")
