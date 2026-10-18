from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.contracts import FinancialFact, Report, StatementType, VerificationStatus

METRICS: dict[str, tuple[str, StatementType, tuple[str, ...]]] = {
    "revenue": ("营业收入", StatementType.INCOME, ("营业收入",)),
    "net_profit_parent": ("归属于上市公司股东的净利润", StatementType.INCOME, ("归属于上市公司股东的净利润",)),
    "deducted_net_profit": ("扣除非经常性损益后的净利润", StatementType.INCOME, (
        "归属于上市公司股东的扣除非经常性损益的净利润",
        "归属于上市公司股东的扣除非经常性损益后的净利润",
        "扣除非经常性损益后的净利润",
    )),
    "operating_cashflow": ("经营活动产生的现金流量净额", StatementType.CASHFLOW, ("经营活动产生的现金流量净额",)),
    "accounts_receivable": ("应收账款", StatementType.BALANCE, ("应收账款",)),
    "inventory": ("存货", StatementType.BALANCE, ("存货",)),
}

NUMBER = r"[-+]?\(?\d[\d,，]*(?:\.\d+)?\)?"
MULTIPLIER = {"元": 1, "千元": 1_000, "万元": 10_000, "亿元": 100_000_000}


def _to_float(raw: str) -> float:
    cleaned = raw.strip()
    negative = (cleaned.startswith("(") and cleaned.endswith(")")) or cleaned.startswith("-")
    number = float(cleaned.strip("()+-").replace(",", "").replace("，", ""))
    return -number if negative else number


def _flexible_label(label: str) -> str:
    return r"\s*".join(re.escape(char) for char in label)


def _unit(text: str) -> str | None:
    match = re.search(r"(?:金额)?单位[^\n]{0,20}?(亿元|万元|千元|元)", text)
    return match.group(1) if match else None


def _fact(report: Report, metric_code: str, page: dict[str, object], raw: str, unit: str | None, excerpt: str) -> FinancialFact:
    metric_name, statement_type, _ = METRICS[metric_code]
    raw_value = _to_float(raw)
    year = int(report.report_period[:4])
    return FinancialFact(
        report_id=report.report_id,
        company_code=report.company_code,
        report_period=report.report_period,
        report_year=year,
        metric_code=metric_code,
        metric_name=metric_name,
        value=raw_value * MULTIPLIER[unit] if unit else None,
        unit=report.currency,
        raw_value=raw_value,
        raw_unit=unit or "",
        statement_type=statement_type,
        source_file=report.original_filename,
        page_number=int(page["page_number"]),
        source_text=excerpt,
        extraction_method="current_year_consolidated_table" if unit else "unit_requires_review",
        verification_status=VerificationStatus.EXTRACTED if unit else VerificationStatus.REVIEW_REQUIRED,
    )


def _summary_facts(report: Report, pages: list[dict[str, object]]) -> list[FinancialFact]:
    for page in pages[:25]:
        text = str(page["text"])
        if not ("主要会计数据" in text and "营业收入" in text and "经营活动产生的现金流量" in text):
            continue
        header = text[: text.find("营业收入")]
        if str(int(report.report_period[:4])) not in header:
            continue
        section = text[text.find("主要会计数据") :]
        section = section.split("(二) 主要财务指标")[0]
        section = section.split("（二）主要财务指标")[0]
        page_unit = _unit(header)
        facts: list[FinancialFact] = []
        for metric_code in ("revenue", "net_profit_parent", "deducted_net_profit", "operating_cashflow"):
            _, _, aliases = METRICS[metric_code]
            for alias in aliases:
                pattern = re.compile(_flexible_label(alias) + rf"(?:\s*[（(](亿元|万元|千元|元)[）)])?\s*({NUMBER})")
                match = pattern.search(section)
                if match is None:
                    continue
                unit = _unit("单位：" + (match.group(1) or "")) if match.group(1) else page_unit
                excerpt = section[max(0, match.start() - 32) : min(len(section), match.end() + 85)].replace("\n", " ")
                facts.append(_fact(report, metric_code, page, match.group(2), unit, excerpt))
                break
        return facts
    return []


def _balance_facts(report: Report, pages: list[dict[str, object]]) -> list[FinancialFact]:
    for index, page in enumerate(pages[20:], start=20):
        text = str(page["text"])
        title = "合并及公司资产负债表" if "合并及公司资产负债表" in text else "合并资产负债表" if "合并资产负债表" in text else ""
        if not title or "单位" not in text[text.find(title) : text.find(title) + 180]:
            continue
        start = text.find(title)
        unit = _unit(text[start : start + 200])
        facts: list[FinancialFact] = []
        for candidate in pages[index : index + 3]:
            candidate_text = str(candidate["text"])
            if candidate is page:
                candidate_text = candidate_text[start:]
            if "母公司资产负债表" in candidate_text and title != "合并及公司资产负债表":
                candidate_text = candidate_text.split("母公司资产负债表")[0]
            for metric_code in ("accounts_receivable", "inventory"):
                if any(fact.metric_code == metric_code for fact in facts):
                    continue
                label = METRICS[metric_code][0]
                row = next((line for line in candidate_text.splitlines() if re.match(rf"^\s*{label}\s+", line)), None)
                if not row:
                    continue
                rest = re.sub(rf"^\s*{label}\s+", "", row)
                rest = re.sub(r"^(?:四\(\d+\)|\d{1,2})\s+", "", rest)
                number = re.match(NUMBER, rest)
                if number:
                    facts.append(_fact(report, metric_code, candidate, number.group(), unit, row.strip()))
            if len(facts) == 2:
                return facts
        return facts
    return []


def extract_financial_facts(report: Report, pages: Iterable[dict[str, object]]) -> list[FinancialFact]:
    """Read the current-year column from the summary and consolidated balance sheet only."""
    page_list = list(pages)
    return _summary_facts(report, page_list) + _balance_facts(report, page_list)
