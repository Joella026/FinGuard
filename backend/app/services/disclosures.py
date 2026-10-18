from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests
from pydantic import BaseModel

from app.config import DATA_DIR
from app.models.contracts import Report
from app.services.report_store import list_reports, save_report
from app.tools.audit import sha256_file


CNINFO = "https://www.cninfo.com.cn"
PDF_HOST = "https://static.cninfo.com.cn"
CATEGORIES = {
    "annual": ("年度报告", "category_ndbg_szsh", "FY", "annual_report"),
    "semiannual": ("半年度报告", "category_bndbg_szsh", "H1", "semiannual_report"),
    "q1": ("第一季度报告", "category_yjdbg_szsh", "Q1", "quarterly_report"),
    "q3": ("第三季度报告", "category_sjdbg_szsh", "Q3", "quarterly_report"),
}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36", "Referer": f"{CNINFO}/", "Accept": "application/json"}
MAX_PDF_BYTES = 80 * 1024 * 1024


def _request(method: str, url: str, **kwargs) -> requests.Response:
    direct = requests.Session()
    direct.trust_env = False
    try:
        response = direct.request(method, url, **kwargs)
        response._finguard_session = direct
        return response
    except requests.RequestException:
        direct.close()
        return requests.request(method, url, **kwargs)


class Disclosure(BaseModel):
    announcement_id: str
    company_code: str
    company_name: str
    title: str
    report_year: int
    kind: str
    kind_label: str
    report_period: str
    published_at: str
    pdf_url: str | None = None
    local_report_id: str | None = None
    is_summary: bool = False
    is_correction: bool = False


class DisclosureSearch(BaseModel):
    company_code: str
    items: list[Disclosure]
    upstream_available: bool
    warning: str | None = None


def normalize_code(code: str) -> str:
    code = code.strip().upper().removesuffix(".SZ").removesuffix(".SH").removesuffix(".BJ")
    if not re.fullmatch(r"\d{6}", code):
        raise ValueError("请输入 6 位 A 股股票代码，例如 000333")
    return code


def _year(title: str) -> int | None:
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", title)
    return int(match.group(1)) if match else None


def _pdf_url(path: str) -> str:
    path = path.lstrip("/")
    if not re.fullmatch(r"(?:finalpage|new)/[A-Za-z0-9_./-]+\.PDF", path, re.IGNORECASE) or ".." in path:
        raise ValueError("公告 PDF 地址无效")
    return f"{PDF_HOST}/{path}"


def _stock_org_id(code: str) -> str:
    response = _request("GET", f"{CNINFO}/new/data/szse_stock.json", headers=HEADERS, timeout=12)
    response.raise_for_status()
    stocks = response.json().get("stockList", [])
    for stock in stocks:
        if stock.get("code") == code:
            return str(stock["orgId"])
    raise ValueError(f"巨潮股票目录中未找到 {code}")


def _query_category(code: str, org_id: str, kind: str, year_from: int, year_to: int) -> list[Disclosure]:
    label, category, suffix, _ = CATEGORIES[kind]
    result: list[Disclosure] = []
    for page in range(1, 4):
        payload = {
            "pageNum": str(page), "pageSize": "30", "column": "szse", "tabName": "fulltext",
            "plate": "", "stock": f"{code},{org_id}", "searchkey": "", "secid": "",
            "category": category, "trade": "", "seDate": f"{year_from}-01-01~{year_to + 1}-12-31",
            "sortName": "", "sortType": "", "isHLtitle": "false",
        }
        response = _request("POST", f"{CNINFO}/new/hisAnnouncement/query", data=payload, headers=HEADERS, timeout=15)
        response.raise_for_status()
        body = response.json()
        announcements = body.get("announcements") or []
        for announcement in announcements:
            if str(announcement.get("secCode")) != code:
                continue
            title = re.sub(r"<[^>]*>", "", str(announcement.get("announcementTitle", "")))
            year = _year(title)
            if year is None or not year_from <= year <= year_to:
                continue
            try:
                pdf_url = _pdf_url(str(announcement.get("adjunctUrl", "")))
            except ValueError:
                continue
            published = announcement.get("announcementTime")
            published_at = datetime.fromtimestamp(published / 1000, timezone.utc).isoformat() if isinstance(published, (int, float)) else str(published or "")
            result.append(Disclosure(
                announcement_id=str(announcement["announcementId"]), company_code=code,
                company_name=str(announcement.get("secName") or code), title=title,
                report_year=year, kind=kind, kind_label=label, report_period=f"{year}{suffix}",
                published_at=published_at, pdf_url=pdf_url,
                is_summary="摘要" in title, is_correction=any(token in title for token in ("更正", "修订", "补充")),
            ))
        if len(announcements) < 30:
            break
    return result


def _local_items(code: str) -> list[Disclosure]:
    items: list[Disclosure] = []
    kind_by_period = {"FY": "annual", "H1": "semiannual", "Q1": "q1", "Q3": "q3"}
    for report in list_reports():
        if report.company_code != code:
            continue
        suffix = report.report_period[4:]
        kind = kind_by_period.get(suffix)
        if kind is None:
            continue
        filename_title = report.original_filename.removesuffix(".pdf").removesuffix(".PDF")
        title = f"{report.company_name or code} {report.report_period[:4]} 年{CATEGORIES[kind][0]}" if re.fullmatch(r"\d{6}_\d{4}_[A-Za-z0-9_-]+", filename_title) else filename_title
        items.append(Disclosure(
            announcement_id=report.announcement_id or f"local:{report.report_id}",
            company_code=code, company_name=report.company_name or code,
            title=title,
            report_year=int(report.report_period[:4]), kind=kind, kind_label=CATEGORIES[kind][0],
            report_period=report.report_period, published_at=report.uploaded_at.isoformat(),
            pdf_url=report.source_url, local_report_id=report.report_id,
            is_summary="摘要" in title, is_correction=any(token in title for token in ("更正", "修订", "补充")),
        ))
    return items


def search_disclosures(code: str, year_from: int, year_to: int) -> DisclosureSearch:
    code = normalize_code(code)
    if not 1990 <= year_from <= year_to <= datetime.now().year or year_to - year_from > 9:
        raise ValueError("搜索年份范围须在 1990 年至今，跨度不超过 10 年")
    local = _local_items(code)
    try:
        org_id = _stock_org_id(code)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda kind: _query_category(code, org_id, kind, year_from, year_to), CATEGORIES))
        remote = [item for group in results for item in group]
    except (requests.RequestException, KeyError, ValueError, TypeError) as error:
        if not local:
            raise ConnectionError("巨潮资讯当前无法连接，请检查网络或稍后重试") from error
        return DisclosureSearch(company_code=code, items=[item for item in local if year_from <= item.report_year <= year_to], upstream_available=False, warning="巨潮资讯当前无法连接，仅显示本机已保存报告。")
    local_by_announcement = {item.announcement_id: item for item in local}
    local_by_period = {(item.report_period, item.title): item for item in local}
    for item in remote:
        cached = local_by_announcement.get(item.announcement_id) or local_by_period.get((item.report_period, item.title))
        if cached:
            item.local_report_id = cached.local_report_id
    seen = {item.local_report_id for item in remote if item.local_report_id}
    remote.extend(item for item in local if item.local_report_id not in seen and year_from <= item.report_year <= year_to)
    remote.sort(key=lambda item: (item.report_year, item.published_at), reverse=True)
    return DisclosureSearch(company_code=code, items=remote, upstream_available=True)


def import_disclosure(code: str, announcement_id: str, year: int) -> Report:
    code = normalize_code(code)
    if announcement_id.startswith("local:"):
        report = next((item for item in list_reports() if item.report_id == announcement_id.removeprefix("local:") and item.company_code == code), None)
        if report is None:
            raise FileNotFoundError("本机报告不存在")
        return report
    search = search_disclosures(code, year, year)
    item = next((entry for entry in search.items if entry.announcement_id == announcement_id and entry.pdf_url), None)
    if item is None:
        raise FileNotFoundError("未在巨潮检索结果中找到该公告")
    if item.local_report_id:
        return next(report for report in list_reports() if report.report_id == item.local_report_id)
    if item.is_summary or item.is_correction:
        raise ValueError("请先选择完整正本报告；摘要或修订公告不自动导入分析")
    parsed = urlparse(item.pdf_url)
    if parsed.scheme != "https" or parsed.netloc != "static.cninfo.com.cn":
        raise ValueError("公告 PDF 来源不受信任")
    report = Report(
        company_code=code, company_name=item.company_name, report_period=item.report_period,
        report_type=CATEGORIES[item.kind][3], original_filename=f"{code}_{item.report_period}_{announcement_id}.pdf",
        stored_path="", sha256="", source_url=item.pdf_url, announcement_id=announcement_id,
    )
    target = DATA_DIR / "raw_reports" / f"{report.report_id}.pdf"
    try:
        with _request("GET", item.pdf_url, headers=HEADERS, timeout=(10, 60), stream=True) as response:
            response.raise_for_status()
            length = 0
            with target.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    length += len(chunk)
                    if length > MAX_PDF_BYTES:
                        raise ValueError("报告超过 80 MB，已停止下载")
                    handle.write(chunk)
        with target.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise ValueError("公告下载内容不是 PDF")
        report.stored_path = str(target)
        report.sha256 = sha256_file(target)
        existing = next((saved for saved in list_reports() if saved.company_code == code and saved.report_period == report.report_period and saved.sha256 == report.sha256), None)
        if existing:
            target.unlink(missing_ok=True)
            existing.announcement_id = existing.announcement_id or announcement_id
            existing.source_url = existing.source_url or item.pdf_url
            save_report(existing)
            return existing
        save_report(report)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return report
