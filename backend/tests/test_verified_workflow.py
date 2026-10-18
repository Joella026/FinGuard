import json

import pytest

from app.models.contracts import AnalysisRunRequest, FactReviewRequest, VerificationStatus
from app.services import analysis, extraction_store
from app.services.demo_cases import load_demo_case
from app.services.extraction_store import review_fact


def prepare_paths(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    runs_dir = tmp_path / "runs"
    (data_dir / "extractions").mkdir(parents=True)
    runs_dir.mkdir()
    monkeypatch.setattr(extraction_store, "DATA_DIR", data_dir)
    monkeypatch.setattr(analysis, "RUNS_DIR", runs_dir)
    return runs_dir


def test_demo_case_runs_end_to_end(monkeypatch, tmp_path):
    runs_dir = prepare_paths(monkeypatch, tmp_path)
    batch = load_demo_case("synthetic-manufacturing-2024-2025")
    result = analysis.run_analysis(AnalysisRunRequest(extraction_id=batch.extraction_id))
    assert len(result.signals) == 4
    assert all(item.status == "triggered" for item in result.rule_assessments)
    assert (runs_dir / result.run.run_id / "final_report.html").exists()
    payload = json.loads((runs_dir / result.run.run_id / "final_result.json").read_text(encoding="utf-8"))
    assert payload["summary"] == result.summary


def test_unreviewed_fact_blocks_analysis(monkeypatch, tmp_path):
    prepare_paths(monkeypatch, tmp_path)
    batch = load_demo_case("synthetic-manufacturing-2024-2025")
    batch.facts[0].verification_status = VerificationStatus.REVIEW_REQUIRED
    extraction_store.save_extraction(batch)
    with pytest.raises(ValueError, match="尚未确认"):
        analysis.run_analysis(AnalysisRunRequest(extraction_id=batch.extraction_id))


def test_review_change_keeps_revision(monkeypatch, tmp_path):
    prepare_paths(monkeypatch, tmp_path)
    batch = load_demo_case("synthetic-manufacturing-2024-2025")
    fact = batch.facts[0]
    updated = review_fact(
        batch.extraction_id,
        fact.fact_id,
        FactReviewRequest(action="verify", value=101, raw_unit="亿元", reason="与原文表格复核"),
    )
    changed = next(item for item in updated.facts if item.fact_id == fact.fact_id)
    assert changed.value == 10_100_000_000
    assert changed.revisions[0].reason == "与原文表格复核"
