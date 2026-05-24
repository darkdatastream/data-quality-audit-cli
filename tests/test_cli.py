import subprocess
import sys
from pathlib import Path


def test_cli_run_writes_reports(tmp_path: Path) -> None:
    out_dir = tmp_path / "audit_report"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "dq_audit",
            "run",
            "--input",
            "examples/dirty_customers.csv",
            "--rules",
            "examples/customer_rules.yaml",
            "--out",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "DATA_QUALITY_AUDIT_COMPLETE" in completed.stdout
    assert "issues=8" in completed.stdout

    assert (out_dir / "summary.md").exists()
    assert (out_dir / "metrics.json").exists()
    assert (out_dir / "summary.html").exists()
    assert (out_dir / "flagged_rows.csv").exists()

    flagged_rows = (out_dir / "flagged_rows.csv").read_text(encoding="utf-8")
    assert "bob.example.com" in flagged_rows
    assert "not-a-date" in flagged_rows
