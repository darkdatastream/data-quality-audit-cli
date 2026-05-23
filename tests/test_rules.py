from pathlib import Path

import pytest

from dq_audit.rules import load_rules


def test_load_rules_from_example_file() -> None:
    ruleset = load_rules("examples/customer_rules.yaml")

    assert ruleset.dataset == "customers"
    assert len(ruleset.rules) == 12
    assert ruleset.rules[0]["type"] == "required_column"


def test_load_rules_rejects_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_rules("examples/does_not_exist.yaml")


def test_load_rules_rejects_invalid_rule_type(tmp_path: Path) -> None:
    rules_file = tmp_path / "bad_rules.yaml"
    rules_file.write_text(
        """
dataset: test
rules:
  - type: not_a_real_rule
    column: customer_id
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported type"):
        load_rules(rules_file)
