from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class StatementType(StrEnum):
    INCOME = "income_statement"
    BALANCE = "balance_sheet"
    CASHFLOW = "cashflow_statement"
    OTHER = "other"


class VerificationStatus(StrEnum):
    EXTRACTED = "extracted"
    VERIFIED = "verified"
    REVIEW_REQUIRED = "review_required"
    MISSING = "missing"


class ExtractionStatus(StrEnum):
    REVIEW_REQUIRED = "review_required"
    READY = "ready"


class Report(BaseModel):
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    company_code: str
    company_name: str | None = None
    currency: str = "CNY"
    report_period: str
    report_type: str
    original_filename: str
    stored_path: str
    sha256: str
    source_url: str | None = None
    announcement_id: str | None = None
    uploaded_at: datetime = Field(default_factory=utc_now)


class FactRevision(BaseModel):
    previous_value: float | None = None
    new_value: float | None = None
    previous_unit: str | None = None
    new_unit: str | None = None
    reason: str
    changed_at: datetime = Field(default_factory=utc_now)


class FinancialFact(BaseModel):
    fact_id: str = Field(default_factory=lambda: str(uuid4()))
    report_id: str
    company_code: str
    report_period: str
    metric_code: str
    metric_name: str
    value: float | None
    unit: str = "CNY"
    raw_value: float | None = None
    raw_unit: str = "元"
    report_year: int | None = None
    scope: str = "consolidated"
    statement_type: StatementType = StatementType.OTHER
    source_file: str
    page_number: int
    table_name: str | None = None
    source_text: str
    extraction_method: str = "pdf_text_regex"
    verification_status: VerificationStatus = VerificationStatus.EXTRACTED
    review_note: str | None = None
    reviewed_at: datetime | None = None
    revisions: list[FactRevision] = Field(default_factory=list)


class MetricCalculation(BaseModel):
    calculation_id: str = Field(default_factory=lambda: str(uuid4()))
    metric_code: str
    metric_name: str
    report_period: str
    formula: str
    input_fact_ids: list[str]
    result: float | None
    unit: str = "ratio"
    rounding_rule: str = "full_precision"
    status: str = "calculated"
    note: str | None = None


class EvidenceLink(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid4()))
    fact_id: str
    source_file: str
    page_number: int
    excerpt: str


class AnomalySignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    rule_id: str
    title: str
    severity: str
    report_period: str
    fact_ids: list[str]
    calculation_ids: list[str] = Field(default_factory=list)
    interpretation: str
    follow_up: str
    counter_evidence: list[str] = Field(default_factory=list)


class RuleAssessment(BaseModel):
    rule_id: str
    title: str
    status: str
    reason: str
    steps: list[dict] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    possible_explanations: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)


class AgentRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    report_ids: list[str]
    company_code: str
    status: str = "queued"
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    model: str | None = None
    git_commit: str | None = None
    output_path: str | None = None


class ExtractionBatch(BaseModel):
    extraction_id: str = Field(default_factory=lambda: str(uuid4()))
    report_ids: list[str]
    company_code: str
    company_name: str | None = None
    years: list[int]
    status: ExtractionStatus = ExtractionStatus.REVIEW_REQUIRED
    facts: list[FinancialFact]
    issues: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ExtractionCreateRequest(BaseModel):
    report_ids: list[str] = Field(min_length=1, max_length=2)


class FactReviewRequest(BaseModel):
    action: str = Field(pattern="^(verify|mark_missing)$")
    value: float | None = None
    raw_unit: str | None = None
    page_number: int | None = Field(default=None, ge=0)
    source_text: str | None = None
    reason: str | None = None


class AnalysisRunRequest(BaseModel):
    extraction_id: str | None = None
    report_ids: list[str] = Field(default_factory=list)
    company_code: str | None = None
    analysis_goal: str = "财务指标提取、业绩变化及异常信号分析"
    use_gpt_narrative: bool = False


class AnalysisResult(BaseModel):
    run: AgentRun
    facts: list[FinancialFact]
    calculations: list[MetricCalculation]
    signals: list[AnomalySignal]
    narrative: str | None = None
    report_url: str
    summary: str = ""
    narrative_error: str | None = None
    rule_assessments: list[RuleAssessment] = Field(default_factory=list)


class DemoCase(BaseModel):
    case_id: str
    name: str
    company_code: str
    company_name: str
    years: list[int]
    description: str
    synthetic: bool = True


class HistoryItem(BaseModel):
    id: str
    kind: str
    company_code: str
    company_name: str | None = None
    years: list[int]
    status: str
    created_at: datetime
    updated_at: datetime
    extraction_id: str | None = None
    run_id: str | None = None

