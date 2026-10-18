import json

import pytest

from app.models.contracts import AgentRun, AnalysisResult, ExtractionBatch
from app.services import history


def test_history_retains_pending_batches_and_individual_runs(monkeypatch, tmp_path):
    data = tmp_path / "data"
    runs = tmp_path / "runs"
    (data / "extractions").mkdir(parents=True)
    runs.mkdir()
    monkeypatch.setattr(history, "DATA_DIR", data)
    monkeypatch.setattr(history, "RUNS_DIR", runs)
    ready = ExtractionBatch(report_ids=["one", "two"], company_code="000333", company_name="美的集团", years=[2024, 2025], facts=[])
    pending = ExtractionBatch(report_ids=["three", "four"], company_code="600519", company_name="贵州茅台", years=[2024, 2025], facts=[])
    for batch in (ready, pending):
        (data / "extractions" / f"{batch.extraction_id}.json").write_text(batch.model_dump_json(), encoding="utf-8")
    for _ in range(2):
        run = AgentRun(report_ids=ready.report_ids, company_code=ready.company_code, status="completed")
        folder = runs / run.run_id
        folder.mkdir()
        result = AnalysisResult(run=run, facts=[], calculations=[], signals=[], report_url="/report")
        (folder / "final_result.json").write_text(result.model_dump_json(), encoding="utf-8")
        (folder / "manifest.json").write_text(json.dumps({"extraction_id": ready.extraction_id}), encoding="utf-8")
    items = history.list_history()
    assert len(items) == 3
    assert sum(item.kind == "analysis" for item in items) == 2
    assert next(item for item in items if item.kind == "review").extraction_id == pending.extraction_id


def test_corrupt_history_is_explicit_error(monkeypatch, tmp_path):
    data = tmp_path / "data"
    (data / "extractions").mkdir(parents=True)
    (data / "extractions" / "broken.json").write_text("{", encoding="utf-8")
    monkeypatch.setattr(history, "DATA_DIR", data)
    monkeypatch.setattr(history, "RUNS_DIR", tmp_path / "runs")
    with pytest.raises(ValueError, match="核验记录损坏"):
        history.list_history()
