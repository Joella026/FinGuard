import type { AnalysisResult, DisclosureSearch, ExtractionBatch, HistoryItem, Report } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let message = `请求失败（${response.status}）`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      message = await response.text() || message;
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),
  history: () => request<HistoryItem[]>("/api/history"),
  searchDisclosures: (code: string, yearFrom: number, yearTo: number) => request<DisclosureSearch>(`/disclosures/search?code=${encodeURIComponent(code)}&year_from=${yearFrom}&year_to=${yearTo}`),
  importDisclosure: (code: string, announcementId: string, year: number) => request<Report>("/disclosures/import", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_code: code, announcement_id: announcementId, report_year: year })
  }),
  uploadReport: async (file: File, companyCode: string | undefined, companyName: string, year: number, period: "FY" | "H1" | "Q1" | "Q2" | "Q3" | "Q4" = "FY", currency = "CNY") => {
    const data = new FormData();
    data.append("file", file);
    data.append("company_code", companyCode || "");
    data.append("company_name", companyName);
    data.append("currency", currency);
    data.append("report_period", `${year}${period}`);
    data.append("report_type", period === "FY" ? "annual_report" : period === "H1" ? "semiannual_report" : "quarterly_report");
    return request<Report>("/reports/upload", { method: "POST", body: data });
  },
  createExtraction: (reportIds: string[]) => request<ExtractionBatch>("/extractions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report_ids: reportIds })
  }),
  extraction: (id: string) => request<ExtractionBatch>(`/extractions/${id}`),
  reviewFact: (extractionId: string, factId: string, body: Record<string, unknown>) => request<ExtractionBatch>(
    `/extractions/${extractionId}/facts/${factId}`,
    { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
  ),
  runAnalysis: (extractionId: string, useGpt: boolean) => request<AnalysisResult>("/analysis/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ extraction_id: extractionId, use_gpt_narrative: useGpt })
  }),
  result: (runId: string) => request<AnalysisResult>(`/analysis/runs/${runId}`)
};
