"""Command line interface for data quality audits."""

from __future__ import annotations

import argparse
from pathlib import Path

from dq_audit.audit import audit_dataframe
from dq_audit.io import read_dataset
from dq_audit.report import write_reports
from dq_audit.rules import load_rules


def build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="dq-audit",
        description="Audit messy CSV and Parquet datasets using YAML validation rules.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Run a data quality audit and write reports.",
    )
    run_parser.add_argument(
        "--input",
        required=True,
        help="Path to the input CSV or Parquet file.",
    )
    run_parser.add_argument(
        "--rules",
        required=True,
        help="Path to the YAML rules file.",
    )
    run_parser.add_argument(
        "--out",
        required=True,
        help="Output directory for generated reports.",
    )
    run_parser.set_defaults(func=run_command)

    return parser


def run_command(args: argparse.Namespace) -> int:
    """Run an audit from CLI arguments."""
    df = read_dataset(args.input)
    ruleset = load_rules(args.rules)
    result = audit_dataframe(df, ruleset)

    write_reports(result, args.out)

    status = "PASS" if result.passed else "FAIL"
    output_dir = Path(args.out)

    print("DATA_QUALITY_AUDIT_COMPLETE")
    print(f"dataset={result.dataset}")
    print(f"status={status}")
    print(f"rows={result.row_count}")
    print(f"columns={result.column_count}")
    print(f"issues={len(result.issues)}")
    print(f"summary_md={output_dir / 'summary.md'}")
    print(f"metrics_json={output_dir / 'metrics.json'}")
    print(f"summary_html={output_dir / 'summary.html'}")
    print(f"flagged_rows_csv={output_dir / 'flagged_rows.csv'}")

    return 0


def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
