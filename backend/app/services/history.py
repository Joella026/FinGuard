from __future__ import annotations

import json
from pathlib import Path

from app.config import DATA_DIR, RUNS_DIR
from app.models.contracts import AnalysisResult, ExtractionBatch, HistoryItem


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"历史记录文件无法读取：{path.name}") from error


def list_history() -> list[HistoryItem]:
    batches: dict[str, ExtractionBatch] = {}
    for path in sorted((DATA_DIR / "extractions").glob("*.json")):
        try:
            batch = ExtractionBatch.model_validate(_read_json(path))
        except Exception as error:
            raise ValueError(f"核验记录损坏：{path.name}") from error
        batches[batch.extraction_id] = batch

    items: list[HistoryItem] = []
    analyzed_batches: set[str] = set()
    for path in sorted(RUNS_DIR.glob("*/final_result.json")):
        try:
            result = AnalysisResult.model_validate(_read_json(path))
            manifest = _read_json(path.parent / "manifest.json")
        except Exception as error:
            raise ValueError(f"分析记录损坏：{path.parent.name}") from error
        extraction_id = manifest.get("extraction_id")
        batch = batches.get(extraction_id)
        if extraction_id:
            analyzed_batches.add(extraction_id)
        years = batch.years if batch else sorted({fact.report_year for fact in result.facts if fact.report_year is not None})
        items.append(HistoryItem(
            id=result.run.run_id,
            kind="analysis",
            company_code=result.run.company_code,
            company_name=batch.company_name if batch else None,
            years=years,
            status="completed",
            created_at=result.run.created_at,
            updated_at=result.run.completed_at or result.run.created_at,
            extraction_id=extraction_id,
            run_id=result.run.run_id,
        ))

    for batch in batches.values():
        if batch.extraction_id in analyzed_batches:
            continue
        items.append(HistoryItem(
            id=batch.extraction_id,
            kind="review",
            company_code=batch.company_code,
            company_name=batch.company_name,
            years=batch.years,
            status="ready" if batch.status == "ready" else "review_required",
            created_at=batch.created_at,
            updated_at=batch.updated_at,
            extraction_id=batch.extraction_id,
        ))
    return sorted(items, key=lambda item: item.updated_at, reverse=True)
