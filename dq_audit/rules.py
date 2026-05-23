"""Load and validate YAML audit rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_RULE_TYPES = {
    "required_column",
    "unique",
    "not_null",
    "pattern",
    "allowed_values",
    "numeric_range",
    "date_parse",
}


@dataclass(frozen=True)
class RuleSet:
    """Validated audit rules loaded from YAML."""

    dataset: str
    rules: list[dict[str, Any]]


def load_rules(path: str | Path) -> RuleSet:
    """Load and validate audit rules from a YAML file."""
    rules_path = Path(path)

    if not rules_path.exists():
        raise FileNotFoundError(f"Rules file does not exist: {rules_path}")

    raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))

    if not isinstance(raw, dict):
        raise ValueError("Rules YAML must contain a mapping at the top level.")

    dataset = raw.get("dataset")
    if not isinstance(dataset, str) or not dataset.strip():
        raise ValueError("Rules YAML must contain a non-empty 'dataset' string.")

    rules = raw.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("Rules YAML must contain a non-empty 'rules' list.")

    validated_rules: list[dict[str, Any]] = []

    for index, rule in enumerate(rules, start=1):
        if not isinstance(rule, dict):
            raise ValueError(f"Rule #{index} must be a mapping.")

        rule_type = rule.get("type")
        if rule_type not in SUPPORTED_RULE_TYPES:
            raise ValueError(
                f"Rule #{index} has unsupported type: {rule_type!r}. "
                f"Supported types: {sorted(SUPPORTED_RULE_TYPES)}"
            )

        column = rule.get("column")
        if not isinstance(column, str) or not column.strip():
            raise ValueError(f"Rule #{index} must contain a non-empty 'column' string.")

        _validate_rule_fields(index=index, rule=rule)
        validated_rules.append(rule)

    return RuleSet(dataset=dataset, rules=validated_rules)


def _validate_rule_fields(index: int, rule: dict[str, Any]) -> None:
    """Validate fields required by specific rule types."""
    rule_type = rule["type"]

    if rule_type == "pattern":
        regex = rule.get("regex")
        if not isinstance(regex, str) or not regex:
            raise ValueError(f"Rule #{index} of type 'pattern' must contain 'regex'.")

    if rule_type == "allowed_values":
        values = rule.get("values")
        if not isinstance(values, list) or not values:
            raise ValueError(
                f"Rule #{index} of type 'allowed_values' must contain a non-empty 'values' list."
            )

    if rule_type == "numeric_range":
        has_min = "min" in rule
        has_max = "max" in rule
        if not has_min and not has_max:
            raise ValueError(
                f"Rule #{index} of type 'numeric_range' must contain 'min' or 'max'."
            )

    if rule_type == "date_parse":
        date_format = rule.get("format")
        if not isinstance(date_format, str) or not date_format:
            raise ValueError(f"Rule #{index} of type 'date_parse' must contain 'format'.")
