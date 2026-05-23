"""Run data quality audits on Polars DataFrames."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import polars as pl

from dq_audit.rules import RuleSet


@dataclass(frozen=True)
class AuditIssue:
    """Single audit issue produced by a validation rule."""

    rule_type: str
    column: str
    message: str
    failed_rows: int


@dataclass(frozen=True)
class AuditResult:
    """Full audit result for one dataset."""

    dataset: str
    row_count: int
    column_count: int
    issues: list[AuditIssue]

    @property
    def passed(self) -> bool:
        """Return True when the audit found no issues."""
        return not self.issues

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable result dictionary."""
        return {
            "dataset": self.dataset,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "passed": self.passed,
            "issue_count": len(self.issues),
            "issues": [asdict(issue) for issue in self.issues],
        }


def audit_dataframe(df: pl.DataFrame, ruleset: RuleSet) -> AuditResult:
    """Audit a Polars DataFrame using a validated RuleSet."""
    issues: list[AuditIssue] = []

    for rule in ruleset.rules:
        rule_type = str(rule["type"])
        column = str(rule["column"])

        if rule_type == "required_column":
            _check_required_column(df=df, column=column, issues=issues)
            continue

        if column not in df.columns:
            issues.append(
                AuditIssue(
                    rule_type=rule_type,
                    column=column,
                    message=f"Column '{column}' is missing, so rule '{rule_type}' could not run.",
                    failed_rows=df.height,
                )
            )
            continue

        if rule_type == "unique":
            _check_unique(df=df, column=column, issues=issues)
        elif rule_type == "not_null":
            _check_not_null(df=df, column=column, issues=issues)
        elif rule_type == "pattern":
            _check_pattern(df=df, column=column, regex=str(rule["regex"]), issues=issues)
        elif rule_type == "allowed_values":
            _check_allowed_values(
                df=df,
                column=column,
                values=list(rule["values"]),
                issues=issues,
            )
        elif rule_type == "numeric_range":
            _check_numeric_range(df=df, column=column, rule=rule, issues=issues)
        elif rule_type == "date_parse":
            _check_date_parse(
                df=df,
                column=column,
                date_format=str(rule["format"]),
                issues=issues,
            )

    return AuditResult(
        dataset=ruleset.dataset,
        row_count=df.height,
        column_count=len(df.columns),
        issues=issues,
    )


def _check_required_column(
    df: pl.DataFrame,
    column: str,
    issues: list[AuditIssue],
) -> None:
    if column not in df.columns:
        issues.append(
            AuditIssue(
                rule_type="required_column",
                column=column,
                message=f"Required column '{column}' is missing.",
                failed_rows=0,
            )
        )


def _check_unique(
    df: pl.DataFrame,
    column: str,
    issues: list[AuditIssue],
) -> None:
    failed_rows = df.filter(pl.col(column).is_duplicated()).height
    if failed_rows:
        issues.append(
            AuditIssue(
                rule_type="unique",
                column=column,
                message=f"Column '{column}' contains duplicate values.",
                failed_rows=failed_rows,
            )
        )


def _check_not_null(
    df: pl.DataFrame,
    column: str,
    issues: list[AuditIssue],
) -> None:
    failed_rows = df.filter(pl.col(column).is_null()).height
    if failed_rows:
        issues.append(
            AuditIssue(
                rule_type="not_null",
                column=column,
                message=f"Column '{column}' contains null values.",
                failed_rows=failed_rows,
            )
        )


def _check_pattern(
    df: pl.DataFrame,
    column: str,
    regex: str,
    issues: list[AuditIssue],
) -> None:
    failed_rows = df.filter(
        pl.col(column).is_not_null()
        & pl.col(column)
        .cast(pl.Utf8)
        .str.contains(regex)
        .fill_null(False)
        .not_()
    ).height

    if failed_rows:
        issues.append(
            AuditIssue(
                rule_type="pattern",
                column=column,
                message=f"Column '{column}' contains values that do not match the expected pattern.",
                failed_rows=failed_rows,
            )
        )


def _check_allowed_values(
    df: pl.DataFrame,
    column: str,
    values: list[Any],
    issues: list[AuditIssue],
) -> None:
    failed_rows = df.filter(~pl.col(column).is_in(values)).height
    if failed_rows:
        issues.append(
            AuditIssue(
                rule_type="allowed_values",
                column=column,
                message=f"Column '{column}' contains values outside the allowed set.",
                failed_rows=failed_rows,
            )
        )


def _check_numeric_range(
    df: pl.DataFrame,
    column: str,
    rule: dict[str, Any],
    issues: list[AuditIssue],
) -> None:
    numeric_col = pl.col(column).cast(pl.Float64, strict=False)

    checks = []
    if "min" in rule:
        checks.append(numeric_col < float(rule["min"]))
    if "max" in rule:
        checks.append(numeric_col > float(rule["max"]))

    mask = checks[0]
    for check in checks[1:]:
        mask = mask | check

    failed_rows = df.filter(mask.fill_null(False)).height
    if failed_rows:
        issues.append(
            AuditIssue(
                rule_type="numeric_range",
                column=column,
                message=f"Column '{column}' contains numeric values outside the allowed range.",
                failed_rows=failed_rows,
            )
        )


def _check_date_parse(
    df: pl.DataFrame,
    column: str,
    date_format: str,
    issues: list[AuditIssue],
) -> None:
    parsed = pl.col(column).cast(pl.Utf8).str.strptime(
        pl.Date,
        format=date_format,
        strict=False,
    )

    failed_rows = df.filter(
        pl.col(column).is_not_null() & parsed.is_null()
    ).height

    if failed_rows:
        issues.append(
            AuditIssue(
                rule_type="date_parse",
                column=column,
                message=f"Column '{column}' contains values that cannot be parsed as dates.",
                failed_rows=failed_rows,
            )
        )
