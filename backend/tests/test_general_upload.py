from fastapi.testclient import TestClient
from io import BytesIO
from pypdf import PdfWriter

from app import main
from app.models.contracts import Report
from app.services import extraction, report_store


def test_nonlisted_company_can_upload_without_stock_code(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "raw_reports").mkdir(parents=True)
    (data_dir / "manifests").mkdir()
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(report_store, "DATA_DIR", data_dir)
    client = TestClient(main.app)
    fields = {"company_name": "示例私人公司", "company_code": "", "report_period": "2025FY", "currency": "HKD"}
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=400)
    writer.write(output)
    response = client.post("/reports/upload", data=fields, files={"file": ("report.pdf", output.getvalue(), "application/pdf")})
    assert response.status_code == 200
    payload = response.json()
    assert payload["company_code"].startswith("LOCAL-")
    assert payload["currency"] == "HKD"
    assert report_store.load_report(payload["report_id"]).currency == "HKD"


def test_reject_mixed_currency_comparison():
    common = {"company_code": "PRIVATE", "company_name": "示例", "report_type": "annual_report",
              "original_filename": "report.pdf", "stored_path": "report.pdf", "sha256": "x"}
    one = Report(**common, report_period="2024FY", currency="CNY")
    two = Report(**common, report_period="2025FY", currency="USD")
    try:
        extraction._validate_reports([one, two])
    except ValueError as error:
        assert "币种" in str(error)
    else:
        raise AssertionError("Mixed currency comparison was accepted")
