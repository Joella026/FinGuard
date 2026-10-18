from __future__ import annotations

from app.models.contracts import AnalysisRunRequest


def create_analysis_plan(request: AnalysisRunRequest) -> list[str]:
    """Deterministic first-version planner; it is logged so execution is auditable."""
    steps = [
        "parse_pdf_report",
        "extract_financial_facts",
        "normalize_accounting_basis",
        "calculate_financial_metrics",
        "check_three_statements",
        "detect_anomaly_signals",
        "verify_evidence",
    ]
    if request.use_gpt_narrative:
        steps.append("generate_verified_narrative")
    steps.append("generate_analysis_report")
    return steps

