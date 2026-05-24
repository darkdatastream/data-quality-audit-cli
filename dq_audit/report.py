"""Report writers for audit results."""

from __future__ import annotations

import csv
import io
import json
from html import escape
from pathlib import Path
from typing import Any

from dq_audit.audit import AuditResult


def write_reports(result: AuditResult, out_dir: str | Path) -> None:
    """Write Markdown, JSON, HTML, and flagged rows CSV audit reports."""
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = output_dir / "metrics.json"
    summary_md_path = output_dir / "summary.md"
    summary_html_path = output_dir / "summary.html"
    flagged_rows_path = output_dir / "flagged_rows.csv"

    metrics_path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    summary_md_path.write_text(_build_markdown_summary(result), encoding="utf-8")
    summary_html_path.write_text(_build_html_summary(result), encoding="utf-8")
    flagged_rows_path.write_text(_build_flagged_rows_csv(result), encoding="utf-8")


def _build_markdown_summary(result: AuditResult) -> str:
    status = "PASS" if result.passed else "FAIL"

    lines = [
        f"# Data Quality Audit Summary",
        "",
        f"- Dataset: `{result.dataset}`",
        f"- Status: **{status}**",
        f"- Rows: `{result.row_count}`",
        f"- Columns: `{result.column_count}`",
        f"- Issues: `{len(result.issues)}`",
        f"- Flagged rows: `{len(result.flagged_rows)}`",
        "",
        "## Issues",
        "",
    ]

    if not result.issues:
        lines.append("No issues found.")
    else:
        lines.append("| Rule | Column | Failed rows | Message |")
        lines.append("|---|---:|---:|---|")
        for issue in result.issues:
            lines.append(
                f"| `{issue.rule_type}` | `{issue.column}` | `{issue.failed_rows}` | {issue.message} |"
            )

    lines.append("")
    lines.append("## Flagged rows")
    lines.append("")

    if not result.flagged_rows:
        lines.append("No flagged rows.")
    else:
        lines.append("| Row number | Rule | Column | Current value | Message |")
        lines.append("|---:|---|---|---|---|")
        for row in result.flagged_rows[:50]:
            lines.append(
                f"| `{row.row_number}` | `{row.rule_type}` | `{row.column}` | `{row.current_value}` | {row.message} |"
            )

        if len(result.flagged_rows) > 50:
            lines.append("")
            lines.append(
                f"Showing first 50 flagged rows in this summary. Full output is available in `flagged_rows.csv`."
            )

    lines.append("")
    return "\n".join(lines)


def _build_html_summary(result: AuditResult) -> str:
    status = "PASS" if result.passed else "FAIL"

    if result.issues:
        issue_rows = "\n".join(
            "<tr>"
            f"<td>{escape(issue.rule_type)}</td>"
            f"<td>{escape(issue.column)}</td>"
            f"<td>{issue.failed_rows}</td>"
            f"<td>{escape(issue.message)}</td>"
            "</tr>"
            for issue in result.issues
        )
    else:
        issue_rows = '<tr><td colspan="4">No issues found.</td></tr>'

    if result.flagged_rows:
        flagged_rows = "\n".join(
            "<tr>"
            f"<td>{row.row_number}</td>"
            f"<td>{escape(row.rule_type)}</td>"
            f"<td>{escape(row.column)}</td>"
            f"<td>{escape(_safe_text(row.current_value))}</td>"
            f"<td>{escape(row.message)}</td>"
            "</tr>"
            for row in result.flagged_rows[:100]
        )
    else:
        flagged_rows = '<tr><td colspan="5">No flagged rows.</td></tr>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Data Quality Audit Summary</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #ddd; padding: 0.55rem; text-align: left; }}
    th {{ background: #f4f4f4; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.25rem; border-radius: 0.2rem; }}
  </style>
</head>
<body>
  <h1>Data Quality Audit Summary</h1>
  <p><strong>Dataset:</strong> <code>{escape(result.dataset)}</code></p>
  <p><strong>Status:</strong> {status}</p>
  <p><strong>Rows:</strong> {result.row_count}</p>
  <p><strong>Columns:</strong> {result.column_count}</p>
  <p><strong>Issues:</strong> {len(result.issues)}</p>
  <p><strong>Flagged rows:</strong> {len(result.flagged_rows)}</p>

  <h2>Issues</h2>
  <table>
    <thead>
      <tr>
        <th>Rule</th>
        <th>Column</th>
        <th>Failed rows</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody>
      {issue_rows}
    </tbody>
  </table>

  <h2>Flagged rows</h2>
  <table>
    <thead>
      <tr>
        <th>Row number</th>
        <th>Rule</th>
        <th>Column</th>
        <th>Current value</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody>
      {flagged_rows}
    </tbody>
  </table>
</body>
</html>
"""


def _build_flagged_rows_csv(result: AuditResult) -> str:
    output = io.StringIO()
    fieldnames = ["row_number", "rule_type", "column", "current_value", "message"]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for row in result.flagged_rows:
        writer.writerow(
            {
                "row_number": row.row_number,
                "rule_type": row.rule_type,
                "column": row.column,
                "current_value": _safe_text(row.current_value),
                "message": row.message,
            }
        )

    return output.getvalue()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
