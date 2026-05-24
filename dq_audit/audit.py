"""Run data quality audits on Polars DataFrames."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import polars as pl

from dq_audit.rules import RuleSet


@dataclass(frozen=True)
class AuditIssue:
    """Aggregated audit issue produced by a validation rule."""

    rule_type: str
    column: str
    message: str
    failed_rows: int


@dataclass(frozen=True)
class FlaggedRow:
    """Single row-level data quality finding."""

    row_number: int
    rule_type: str
    column: str
    current_value: Any
    message: str


@dataclass(frozen=True)
class AuditResult:
    """Full audit result for one dataset."""

    dataset: str
    row_count: int
    column_count: int
    issues: list[AuditIssue]
    flagged_rows: list[FlaggedRow] = field(default_factory=list)

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
            "flagged_row_count": len(self.flagged_rows),
            "issues": [asdict(issue) for issue in self.issues],
            "flagged_rows": [asdict(row) for row in self.flagged_rows],
        }


def audit_dataframe(df: pl.DataFrame, ruleset: RuleSet) -> AuditResult:
    """Audit a Polars DataFrame using a validated RuleSet."""
    issues: list[AuditIssue] = []
    flagged_rows: list[FlaggedRow] = []

    df_with_row_numbers = df.with_row_index("_dq_row_number", offset=1)

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
            _check_unique(
                df=df_with_row_numbers,
                column=column,
                issues=issues,
                flagged_rows=flagged_rows,
            )
        elif rule_type == "not_null":
            _check_not_null(
                df=df_with_row_numbers,
                column=column,
                issues=issues,
                flagged_rows=flagged_rows,
            )
        elif rule_type == "pattern":
            _check_pattern(
                df=df_with_row_numbers,
                column=column,
                regex=str(rule["regex"]),
                issues=issues,
                flagged_rows=flagged_rows,
            )
        elif rule_type == "allowed_values":
            _check_allowed_values(
                df=df_with_row_numbers,
                column=column,
                values=list(rule["values"]),
                issues=issues,
                flagged_rows=flagged_rows,
            )
        elif rule_type == "numeric_range":
            _check_numeric_range(
                df=df_with_row_numbers,
                column=column,
                rule=rule,
                issues=issues,
                flagged_rows=flagged_rows,
            )
        elif rule_type == "date_parse":
            _check_date_parse(
                df=df_with_row_numbers,
                column=column,
                date_format=str(rule["format"]),
                issues=issues,
                flagged_rows=flagged_rows,
            )

    return AuditResult(
        dataset=ruleset.dataset,
        row_count=df.height,
        column_count=len(df.columns),
        issues=issues,
        flagged_rows=flagged_rows,
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
    flagged_rows: list[FlaggedRow],
) -> None:
    failed = df.filter(pl.col(column).is_duplicated())
    failed_rows = failed.height

    if failed_rows:
        message = f"Column '{column}' contains duplicate values."
        issues.append(
            AuditIssue(
                rule_type="unique",
                column=column,
                message=message,
                failed_rows=failed_rows,
            )
        )
        _append_flagged_rows(
            failed=failed,
            rule_type="unique",
            column=column,
            message=message,
            flagged_rows=flagged_rows,
        )


def _check_not_null(
    df: pl.DataFrame,
    column: str,
    issues: list[AuditIssue],
    flagged_rows: list[FlaggedRow],
) -> None:
    failed = df.filter(pl.col(column).is_null())
    failed_rows = failed.height

    if failed_rows:
        message = f"Column '{column}' contains null values."
        issues.append(
            AuditIssue(
                rule_type="not_null",
                column=column,
                message=message,
                failed_rows=failed_rows,
            )
        )
        _append_flagged_rows(
            failed=failed,
            rule_type="not_null",
            column=column,
            message=message,
            flagged_rows=flagged_rows,
        )


def _check_pattern(
    df: pl.DataFrame,
    column: str,
    regex: str,
    issues: list[AuditIssue],
    flagged_rows: list[FlaggedRow],
) -> None:
    failed = df.filter(
        pl.col(column).is_not_null()
        & pl.col(column)
        .cast(pl.Utf8)
        .str.contains(regex)
        .fill_null(False)
        .not_()
    )
    failed_rows = failed.height

    if failed_rows:
        message = f"Column '{column}' contains values that do not match the expected pattern."
        issues.append(
            AuditIssue(
                rule_type="pattern",
                column=column,
                message=message,
                failed_rows=failed_rows,
            )
        )
        _append_flagged_rows(
            failed=failed,
            rule_type="pattern",
            column=column,
            message=message,
            flagged_rows=flagged_rows,
        )


def _check_allowed_values(
    df: pl.DataFrame,
    column: str,
    values: list[Any],
    issues: list[AuditIssue],
    flagged_rows: list[FlaggedRow],
) -> None:
    failed = df.filter(pl.col(column).is_not_null() & ~pl.col(column).is_in(values))
    failed_rows = failed.height

    if failed_rows:
        message = f"Column '{column}' contains values outside the allowed set."
        issues.append(
            AuditIssue(
                rule_type="allowed_values",
                column=column,
                message=message,
                failed_rows=failed_rows,
            )
        )
        _append_flagged_rows(
            failed=failed,
            rule_type="allowed_values",
            column=column,
            message=message,
            flagged_rows=flagged_rows,
        )


def _check_numeric_range(
    df: pl.DataFrame,
    column: str,
    rule: dict[str, Any],
    issues: list[AuditIssue],
    flagged_rows: list[FlaggedRow],
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

    failed = df.filter(mask.fill_null(False))
    failed_rows = failed.height

    if failed_rows:
        message = f"Column '{column}' contains numeric values outside the allowed range."
        issues.append(
            AuditIssue(
                rule_type="numeric_range",
                column=column,
                message=message,
                failed_rows=failed_rows,
            )
        )
        _append_flagged_rows(
            failed=failed,
            rule_type="numeric_range",
            column=column,
            message=message,
            flagged_rows=flagged_rows,
        )


def _check_date_parse(
    df: pl.DataFrame,
    column: str,
    date_format: str,
    issues: list[AuditIssue],
    flagged_rows: list[FlaggedRow],
) -> None:
    parsed = pl.col(column).cast(pl.Utf8).str.strptime(
        pl.Date,
        format=date_format,
        strict=False,
    )

    failed = df.filter(pl.col(column).is_not_null() & parsed.is_null())
    failed_rows = failed.height

    if failed_rows:
        message = f"Column '{column}' contains values that cannot be parsed as dates."
        issues.append(
            AuditIssue(
                rule_type="date_parse",
                column=column,
                message=message,
                failed_rows=failed_rows,
            )
        )
        _append_flagged_rows(
            failed=failed,
            rule_type="date_parse",
            column=column,
            message=message,
            flagged_rows=flagged_rows,
        )


def _append_flagged_rows(
    failed: pl.DataFrame,
    rule_type: str,
    column: str,
    message: str,
    flagged_rows: list[FlaggedRow],
) -> None:
    selected = failed.select(["_dq_row_number", column]).to_dicts()

    for row in selected:
        flagged_rows.append(
            FlaggedRow(
                row_number=int(row["_dq_row_number"]),
                rule_type=rule_type,
                column=column,
                current_value=row[column],
                message=message,
            )
        )
