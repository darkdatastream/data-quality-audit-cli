"""Streamlit dashboard for business-facing data quality audits."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import streamlit as st

from dq_audit.audit import AuditResult, audit_dataframe
from dq_audit.io import read_dataset
from dq_audit.report import _build_flagged_rows_csv, _build_html_summary, _build_markdown_summary
from dq_audit.rules import load_rules


st.set_page_config(
    page_title="Data Quality Audit",
    page_icon="📊",
    layout="wide",
)


SEVERITY_BY_RULE = {
    "required_column": "High",
    "unique": "High",
    "not_null": "Medium",
    "pattern": "Medium",
    "allowed_values": "Medium",
    "numeric_range": "High",
    "date_parse": "Medium",
}


BUSINESS_IMPACT_BY_RULE = {
    "required_column": "Required data is missing and downstream imports may fail.",
    "unique": "Duplicate records can create repeated customers, orders, or reports.",
    "not_null": "Missing values can break reporting, segmentation, or import rules.",
    "pattern": "Invalid formats can cause failed communication or rejected imports.",
    "allowed_values": "Unexpected categories can damage filters, dashboards, or reporting.",
    "numeric_range": "Out-of-range numbers can distort financial and operational metrics.",
    "date_parse": "Invalid dates can break timelines, cohorts, and trend reports.",
}


def main() -> None:
    """Render the Streamlit dashboard."""
    _render_styles()

    st.title("Data Quality Audit Dashboard")
    st.caption(
        "Upload a CSV file, run a structured audit, and download business-ready reports."
    )

    with st.sidebar:
        st.header("Audit setup")
        dataset_profile = st.selectbox(
            "Dataset profile",
            ["Customer / CRM data"],
            index=0,
        )
        st.caption(f"Selected profile: {dataset_profile}")

        uploaded_file = st.file_uploader(
            "Upload CSV file",
            type=["csv"],
            accept_multiple_files=False,
        )

        use_example = st.checkbox(
            "Use included demo customer dataset",
            value=uploaded_file is None,
        )

        run_audit = st.button("Run data audit", type="primary", use_container_width=True)

    if not run_audit:
        _render_intro()
        return

    try:
        csv_path = _prepare_input_file(uploaded_file=uploaded_file, use_example=use_example)
        rules_path = Path("examples/customer_rules.yaml")

        df = read_dataset(csv_path)
        ruleset = load_rules(rules_path)
        result = audit_dataframe(df, ruleset)

        _render_result(result)

    except Exception as exc:
        st.error("The audit could not be completed.")
        st.exception(exc)


def _prepare_input_file(uploaded_file: Any, use_example: bool) -> Path:
    if use_example:
        return Path("examples/dirty_customers.csv")

    if uploaded_file is None:
        raise ValueError("Upload a CSV file or enable the demo dataset.")

    temp_dir = tempfile.TemporaryDirectory()
    temp_path = Path(temp_dir.name) / "uploaded.csv"
    temp_path.write_bytes(uploaded_file.getvalue())

    st.session_state["_dq_audit_temp_dir"] = temp_dir
    return temp_path


def _render_intro() -> None:
    left, right = st.columns([1.1, 0.9], gap="large")

    with left:
        st.subheader("What this dashboard does")
        st.write(
            "It checks customer-style CSV data for common business risks: duplicate IDs, "
            "missing values, invalid emails, unexpected categories, negative values, and bad dates."
        )
        st.write(
            "The goal is to catch data problems before import into CRM, reporting, email tools, "
            "or operational systems."
        )

    with right:
        st.subheader("Output")
        st.markdown(
            "- Executive summary\n"
            "- Data quality score\n"
            "- Issue counts by type and column\n"
            "- Business impact table\n"
            "- Downloadable HTML, Markdown, and JSON reports"
        )


def _render_result(result: AuditResult) -> None:
    metrics = result.to_dict()
    quality_score = _quality_score(result)
    status_label = "Ready for review" if result.issues else "Passed"

    st.subheader("Executive summary")

    kpi_1, kpi_2, kpi_3, kpi_4, kpi_5 = st.columns(5)
    kpi_1.metric("Rows analyzed", result.row_count)
    kpi_2.metric("Columns analyzed", result.column_count)
    kpi_3.metric("Issues found", len(result.issues))
    kpi_4.metric("Quality score", f"{quality_score}/100")
    kpi_5.metric("Status", status_label)

    if result.issues:
        st.warning(
            "This dataset should be reviewed before import, reporting, or campaign use."
        )
    else:
        st.success("No issues were found using the selected rules.")

    chart_left, chart_right = st.columns(2, gap="large")

    with chart_left:
        st.markdown("### Issues by rule type")
        _render_bar_chart(_count_by(result, "rule_type"))

    with chart_right:
        st.markdown("### Issues by column")
        _render_bar_chart(_count_by(result, "column"))

    st.markdown("### Business impact table")
    st.dataframe(
        _issue_rows(result),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Exact flagged rows")
    if result.flagged_rows:
        st.dataframe(
            _flagged_row_rows(result),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No flagged rows found.")

    st.markdown("### Downloads")
    html_report = _build_html_summary(result)
    markdown_report = _build_markdown_summary(result)
    metrics_json = json.dumps(metrics, indent=2, ensure_ascii=False) + "\n"
    flagged_rows_csv = _build_flagged_rows_csv(result)

    dl_1, dl_2, dl_3, dl_4 = st.columns(4)
    dl_1.download_button(
        "Download HTML report",
        data=html_report,
        file_name="data_quality_audit_report.html",
        mime="text/html",
        use_container_width=True,
    )
    dl_2.download_button(
        "Download Markdown report",
        data=markdown_report,
        file_name="data_quality_audit_summary.md",
        mime="text/markdown",
        use_container_width=True,
    )
    dl_3.download_button(
        "Download metrics JSON",
        data=metrics_json,
        file_name="data_quality_metrics.json",
        mime="application/json",
        use_container_width=True,
    )
    dl_4.download_button(
        "Download flagged rows CSV",
        data=flagged_rows_csv,
        file_name="flagged_rows.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _issue_rows(result: AuditResult) -> list[dict[str, Any]]:
    return [
        {
            "Severity": SEVERITY_BY_RULE.get(issue.rule_type, "Review"),
            "Rule": issue.rule_type,
            "Column": issue.column,
            "Failed rows": issue.failed_rows,
            "Business impact": BUSINESS_IMPACT_BY_RULE.get(
                issue.rule_type,
                "Review this issue before using the dataset.",
            ),
            "Technical message": issue.message,
        }
        for issue in result.issues
    ]


def _flagged_row_rows(result: AuditResult) -> list[dict[str, Any]]:
    return [
        {
            "Row number": row.row_number,
            "Severity": SEVERITY_BY_RULE.get(row.rule_type, "Review"),
            "Rule": row.rule_type,
            "Column": row.column,
            "Current value": "" if row.current_value is None else row.current_value,
            "Message": row.message,
        }
        for row in result.flagged_rows
    ]


def _count_by(result: AuditResult, field_name: str) -> dict[str, int]:
    counter: Counter[str] = Counter()

    for issue in result.issues:
        value = getattr(issue, field_name)
        counter[str(value)] += int(issue.failed_rows)

    return dict(counter.most_common())


def _quality_score(result: AuditResult) -> int:
    if result.row_count == 0:
        return 0

    failed_cells = sum(issue.failed_rows for issue in result.issues)
    total_cells = max(result.row_count * max(result.column_count, 1), 1)
    score = round(100 - min(100, (failed_cells / total_cells) * 100))
    return max(0, min(100, score))


def _render_bar_chart(values: dict[str, int]) -> None:
    if not values:
        st.info("No issues found.")
        return

    max_value = max(values.values())

    for label, value in values.items():
        percent = int((value / max_value) * 100) if max_value else 0
        st.markdown(
            f"""
            <div class="bar-row">
                <div class="bar-label">{label}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width: {percent}%"></div>
                </div>
                <div class="bar-value">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at 8% 18%, rgba(0, 229, 255, 0.16), transparent 28%),
                radial-gradient(circle at 18% 72%, rgba(236, 0, 140, 0.18), transparent 34%),
                linear-gradient(135deg, #050816 0%, #08051c 46%, #0b1830 100%);
            color: #e5f7ff;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        h1, h2, h3 {
            color: #f8fbff !important;
            letter-spacing: -0.02em;
        }

        p, li, span, label {
            color: #d8efff;
        }

        section[data-testid="stSidebar"] {
            background:
                radial-gradient(circle at 10% 10%, rgba(0, 229, 255, 0.16), transparent 30%),
                linear-gradient(180deg, #07091f 0%, #0c102a 100%);
            border-right: 1px solid rgba(0, 229, 255, 0.18);
        }

        [data-testid="stMetric"] {
            background:
                linear-gradient(135deg, rgba(7, 11, 31, 0.94) 0%, rgba(26, 11, 48, 0.90) 52%, rgba(5, 22, 46, 0.92) 100%);
            border: 1px solid rgba(0, 229, 255, 0.42);
            border-radius: 22px;
            padding: 18px;
            box-shadow:
                0 0 0 1px rgba(236, 0, 140, 0.10),
                0 18px 48px rgba(0, 0, 0, 0.36),
                0 0 34px rgba(0, 229, 255, 0.10);
        }

        [data-testid="stMetricLabel"] {
            color: #8fdfff !important;
            font-weight: 800 !important;
            letter-spacing: 0.02em;
        }

        [data-testid="stMetricValue"] {
            color: #ffffff !important;
            font-weight: 900 !important;
            text-shadow: 0 0 18px rgba(0, 229, 255, 0.18);
        }

        [data-testid="stAlert"] {
            background: rgba(8, 20, 43, 0.86);
            border: 1px solid rgba(0, 229, 255, 0.28);
            border-radius: 16px;
            color: #e5f7ff;
            box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
        }

        [data-testid="stAlert"] div {
            color: #e5f7ff !important;
        }

        .bar-row {
            display: grid;
            grid-template-columns: minmax(150px, 230px) 1fr 64px;
            gap: 14px;
            align-items: center;
            margin: 14px 0;
            font-size: 0.98rem;
        }

        .bar-label {
            color: #aeeaff;
            font-weight: 800;
            overflow-wrap: anywhere;
        }

        .bar-track {
            height: 16px;
            background: rgba(226, 232, 240, 0.16);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 999px;
            overflow: hidden;
            box-shadow: inset 0 0 18px rgba(0, 0, 0, 0.28);
        }

        .bar-fill {
            height: 16px;
            background: linear-gradient(90deg, #00e5ff 0%, #7c3aed 48%, #ec008c 100%);
            border-radius: 999px;
            box-shadow: 0 0 18px rgba(0, 229, 255, 0.26);
        }

        .bar-value {
            font-weight: 900;
            color: #ffffff;
            text-align: right;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(0, 229, 255, 0.22);
            border-radius: 18px;
            overflow: hidden;
            box-shadow: 0 18px 46px rgba(0, 0, 0, 0.28);
        }

        .stDownloadButton button,
        .stButton button {
            background: linear-gradient(90deg, #00e5ff 0%, #7c3aed 52%, #ec008c 100%) !important;
            color: #020617 !important;
            border: 0 !important;
            border-radius: 999px !important;
            font-weight: 900 !important;
            box-shadow: 0 0 30px rgba(0, 229, 255, 0.22);
        }

        .stDownloadButton button:hover,
        .stButton button:hover {
            filter: brightness(1.08);
            box-shadow: 0 0 38px rgba(236, 0, 140, 0.28);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
