import requests
import pytest

from app.models.contracts import Report
from app.services import disclosures


def test_code_and_pdf_path_validation():
    assert disclosures.normalize_code("000333.SZ") == "000333"
    with pytest.raises(ValueError):
        disclosures.normalize_code("../000333")
    assert disclosures._pdf_url("finalpage/2025-04-03/1222993920.PDF").startswith("https://static.cninfo.com.cn/")
    with pytest.raises(ValueError):
        disclosures._pdf_url("https://example.com/report.PDF")


def test_category_query_filters_company_and_extracts_period(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"announcements": [
                {"secCode": "000333", "secName": "美的集团", "announcementTitle": "美的集团：2025年年度报告", "announcementId": "12345", "adjunctUrl": "finalpage/2026-03-01/12345.PDF", "announcementTime": 1772323200000},
                {"secCode": "000001", "announcementTitle": "2025年年度报告", "announcementId": "9", "adjunctUrl": "finalpage/2026-03-01/9.PDF"},
            ]}

    monkeypatch.setattr(disclosures, "_request", lambda *args, **kwargs: Response())
    items = disclosures._query_category("000333", "gssz0000333", "annual", 2024, 2026)
    assert len(items) == 1
    assert items[0].report_period == "2025FY"
    assert items[0].pdf_url == "https://static.cninfo.com.cn/finalpage/2026-03-01/12345.PDF"


def test_offline_search_shows_registered_reports(monkeypatch):
    report = Report(company_code="000333", company_name="美的集团", report_period="2025FY", report_type="annual_report", original_filename="美的2025年年度报告.pdf", stored_path="unused", sha256="abc")
    monkeypatch.setattr(disclosures, "list_reports", lambda: [report])
    monkeypatch.setattr(disclosures, "_stock_org_id", lambda code: (_ for _ in ()).throw(requests.ConnectionError("offline")))
    result = disclosures.search_disclosures("000333", 2024, 2026)
    assert not result.upstream_available
    assert len(result.items) == 1
    assert result.items[0].local_report_id == report.report_id
    with pytest.raises(ConnectionError, match="无法连接"):
        disclosures.search_disclosures("600519", 2024, 2026)


def test_import_downloads_pdf_and_records_provenance(monkeypatch, tmp_path):
    (tmp_path / "raw_reports").mkdir()
    item = disclosures.Disclosure(
        announcement_id="12345", company_code="000333", company_name="美的集团",
        title="美的集团：2025年年度报告", report_year=2025, kind="annual",
        kind_label="年度报告", report_period="2025FY", published_at="2026-03-01",
        pdf_url="https://static.cninfo.com.cn/finalpage/2026-03-01/12345.PDF",
    )
    monkeypatch.setattr(disclosures, "DATA_DIR", tmp_path)
    monkeypatch.setattr(disclosures, "search_disclosures", lambda *_: disclosures.DisclosureSearch(company_code="000333", items=[item], upstream_available=True))
    monkeypatch.setattr(disclosures, "save_report", lambda report: None)
    monkeypatch.setattr(disclosures, "list_reports", lambda: [])

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"%PDF-1.7\nexample"

    monkeypatch.setattr(disclosures, "_request", lambda *_args, **_kwargs: Response())
    report = disclosures.import_disclosure("000333", "12345", 2025)
    assert report.report_period == "2025FY"
    assert report.announcement_id == "12345"
    assert report.sha256
    assert report.source_url == item.pdf_url
