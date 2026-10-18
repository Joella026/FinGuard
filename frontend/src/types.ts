export type VerificationStatus = "extracted" | "verified" | "review_required" | "missing";

export interface Report {
  report_id: string;
  company_code: string;
  company_name?: string;
  currency: string;
  report_period: string;
  original_filename: string;
  report_type?: string;
  source_url?: string;
  announcement_id?: string;
}

export interface Disclosure {
  announcement_id: string;
  company_code: string;
  company_name: string;
  title: string;
  report_year: number;
  kind: "annual" | "semiannual" | "q1" | "q3";
  kind_label: string;
  report_period: string;
  published_at: string;
  pdf_url?: string;
  local_report_id?: string;
  is_summary: boolean;
  is_correction: boolean;
}

export interface DisclosureSearch {
  company_code: string;
  items: Disclosure[];
  upstream_available: boolean;
  warning?: string;
}

export interface FactRevision {
  previous_value?: number;
  new_value?: number;
  previous_unit?: string;
  new_unit?: string;
  reason: string;
  changed_at: string;
}

export interface FinancialFact {
  fact_id: string;
  report_id: string;
  company_code: string;
  report_period: string;
  report_year?: number;
  metric_code: string;
  metric_name: string;
  value?: number;
  unit: string;
  raw_value?: number;
  raw_unit: string;
  source_file: string;
  page_number: number;
  source_text: string;
  extraction_method: string;
  verification_status: VerificationStatus;
  review_note?: string;
  reviewed_at?: string;
  revisions: FactRevision[];
}

export interface ExtractionBatch {
  extraction_id: string;
  report_ids: string[];
  company_code: string;
  company_name?: string;
  years: number[];
  status: "review_required" | "ready";
  facts: FinancialFact[];
  issues: string[];
}

export interface HistoryItem {
  id: string;
  kind: "review" | "analysis";
  company_code: string;
  company_name?: string;
  years: number[];
  status: "review_required" | "ready" | "completed";
  created_at: string;
  updated_at: string;
  extraction_id?: string;
  run_id?: string;
}

export interface Calculation {
  calculation_id: string;
  metric_code: string;
  metric_name: string;
  report_period: string;
  formula: string;
  input_fact_ids: string[];
  result?: number;
  note?: string;
}

export interface Signal {
  signal_id: string;
  rule_id: string;
  title: string;
  severity: string;
  report_period: string;
  fact_ids: string[];
  calculation_ids: string[];
  interpretation: string;
  follow_up: string;
  counter_evidence: string[];
}

export interface RuleAssessment {
  rule_id: string;
  title: string;
  status: "triggered" | "clear" | "insufficient";
  reason: string;
  steps: { label: string; value: number; threshold: number; operator: string; difference: number; passed: boolean; unit: string; formula: string; fact_ids: string[]; calculation_ids: string[]; inputs?: {label: string; value: number}[]; fact_inputs: {fact_id: string; label: string; period: string; value: number; unit: string}[] }[];
  fact_ids: string[];
  calculation_ids: string[];
  missing_inputs: string[];
  possible_explanations: string[];
  next_checks: string[];
}

export interface AnalysisResult {
  run: {
    run_id: string;
    company_code: string;
    status: string;
    completed_at?: string;
    model?: string;
  };
  facts: FinancialFact[];
  calculations: Calculation[];
  signals: Signal[];
  narrative?: string;
  narrative_error?: string;
  summary: string;
  report_url: string;
  rule_assessments: RuleAssessment[];
}
