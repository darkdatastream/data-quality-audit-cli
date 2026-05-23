import polars as pl

from dq_audit.audit import audit_dataframe
from dq_audit.rules import RuleSet


def test_audit_dataframe_detects_expected_issues() -> None:
    df = pl.DataFrame(
        {
            "customer_id": [1, 1, 2],
            "email": ["alice@example.com", "bad-email", None],
            "country": ["PL", "XX", "NL"],
            "age": [34, -1, 40],
        }
    )

    ruleset = RuleSet(
        dataset="customers",
        rules=[
            {"type": "unique", "column": "customer_id"},
            {"type": "not_null", "column": "email"},
            {
                "type": "pattern",
                "column": "email",
                "regex": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            },
            {
                "type": "allowed_values",
                "column": "country",
                "values": ["PL", "NL"],
            },
            {"type": "numeric_range", "column": "age", "min": 0, "max": 120},
        ],
    )

    result = audit_dataframe(df, ruleset)

    assert result.passed is False
    assert result.row_count == 3
    assert result.column_count == 4

    issues = {(issue.rule_type, issue.column): issue.failed_rows for issue in result.issues}

    assert issues[("unique", "customer_id")] == 2
    assert issues[("not_null", "email")] == 1
    assert issues[("pattern", "email")] == 1
    assert issues[("allowed_values", "country")] == 1
    assert issues[("numeric_range", "age")] == 1


def test_audit_dataframe_passes_clean_data() -> None:
    df = pl.DataFrame(
        {
            "customer_id": [1, 2],
            "email": ["alice@example.com", "bob@example.com"],
        }
    )

    ruleset = RuleSet(
        dataset="customers",
        rules=[
            {"type": "required_column", "column": "customer_id"},
            {"type": "unique", "column": "customer_id"},
            {"type": "not_null", "column": "email"},
            {
                "type": "pattern",
                "column": "email",
                "regex": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            },
        ],
    )

    result = audit_dataframe(df, ruleset)

    assert result.passed is True
    assert result.issues == []
