# data-quality-audit-cli

CLI tool for auditing messy CSV and Parquet datasets with Polars, YAML validation rules, and generated Markdown, JSON, and HTML reports.

The project shows a reusable Python package structure instead of a one-off notebook. It is designed as a small portfolio project for data quality checks, validation rules, CLI workflows, automated tests, and GitHub Actions.

## System requirements

Recommended environment:

- Linux, macOS, or Windows with WSL
- Python 3.11 or newer
- Git
- Python virtual environment support

On Debian or Ubuntu, install the required system packages with:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

If a package ever needs local compilation on your system, install build tools as well:

```bash
sudo apt install -y build-essential
```

Native Windows PowerShell/CMD usage is not the primary target for this project. Windows users should use WSL for the same Linux-style commands shown below.

## Quick start from GitHub

Clone the repository:

```bash
git clone https://github.com/darkdatastream/data-quality-audit-cli.git
cd data-quality-audit-cli
```

Create a virtual environment and install the app dependencies:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev,app]"
```

Run the business dashboard:

```bash
.venv/bin/streamlit run app.py
```

Then open the local URL shown in the terminal, usually:

```text
http://localhost:8501
```

To stop the dashboard, press `Ctrl+C` in the terminal.

## CLI usage

Run the included sample audit:

```bash
.venv/bin/dq-audit run --input examples/dirty_customers.csv --rules examples/customer_rules.yaml --out reports/sample
```

The generated reports will be written to:

```text
reports/sample/
├── summary.md
├── metrics.json
├── summary.html
└── flagged_rows.csv
```

## What it does

The tool reads a dataset, applies validation rules from a YAML file, and writes audit reports.

Supported input formats:

- CSV
- Parquet

Supported rule types:

- required column
- unique column
- null checks
- regex pattern checks
- allowed values
- numeric min/max range
- date parsing checks

## Example

Run the audit on the included sample dataset:

```bash
python -m dq_audit run --input examples/dirty_customers.csv --rules examples/customer_rules.yaml --out reports/sample
```

After editable installation, the console command is also available:

```bash
dq-audit run --input examples/dirty_customers.csv --rules examples/customer_rules.yaml --out reports/sample
```

Example CLI output:

```text
DATA_QUALITY_AUDIT_COMPLETE
dataset=customers
status=FAIL
rows=7
columns=8
issues=8
summary_md=reports/sample/summary.md
metrics_json=reports/sample/metrics.json
summary_html=reports/sample/summary.html
flagged_rows_csv=reports/sample/flagged_rows.csv
```

Generated files:

- `summary.md`
- `metrics.json`
- `summary.html`
- `flagged_rows.csv`

## Example rules file

```yaml
dataset: customers

rules:
  - type: required_column
    column: customer_id

  - type: unique
    column: customer_id

  - type: not_null
    column: email

  - type: pattern
    column: email
    regex: '^[^@\s]+@[^@\s]+\.[^@\s]+$'

  - type: allowed_values
    column: country
    values: ["PL", "NL", "DE", "ES"]

  - type: numeric_range
    column: total_spend
    min: 0

  - type: date_parse
    column: signup_date
    format: "%Y-%m-%d"
```

## Project structure

```text
data-quality-audit-cli/
├── app.py
├── dq_audit/
│   ├── __init__.py
│   ├── __main__.py
│   ├── audit.py
│   ├── cli.py
│   ├── io.py
│   ├── report.py
│   └── rules.py
├── tests/
│   ├── test_audit.py
│   ├── test_cli.py
│   └── test_rules.py
├── examples/
│   ├── dirty_customers.csv
│   └── customer_rules.yaml
├── .github/workflows/tests.yml
├── .gitattributes
├── .gitignore
├── pyproject.toml
└── README.md
```

## Business dashboard

The project also includes a Streamlit dashboard for non-technical users.

It provides a browser-based workflow:

- upload a CSV file
- run the audit
- review executive metrics
- view issue charts
- inspect business impact by rule
- download HTML, Markdown, JSON, and flagged rows CSV reports

Run the dashboard locally:

```bash
.venv/bin/python -m pip install -e ".[dev,app]"
.venv/bin/streamlit run app.py
```

The dashboard uses the same audit engine as the CLI. The core validation logic remains in the `dq_audit` package.

## Installation for local development

Create and activate a virtual environment, then install the package with test dependencies:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

Run tests:

```bash
.venv/bin/python -m pytest -q
```

## What this project demonstrates

- Python package structure
- CLI design with `argparse`
- Polars-based data loading and validation
- YAML-driven validation rules
- Markdown, JSON, and HTML report generation
- Automated tests with pytest
- GitHub Actions test workflow
- Safe `.gitignore` setup for local data, virtual environments, and generated reports

## Notes

The included dataset is intentionally small and dirty. It is safe to commit and exists only to demonstrate the validation workflow.

Generated reports are ignored by Git because they are reproducible outputs.
