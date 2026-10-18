from __future__ import annotations

import json
from datetime import UTC, datetime

from app.config import DATA_DIR
from app.models.contracts import ExtractionBatch, ExtractionStatus, FactReviewRequest, FactRevision, VerificationStatus


def extraction_path(extraction_id: str):
    return DATA_DIR / "extractions" / f"{extraction_id}.json"


def save_extraction(batch: ExtractionBatch) -> None:
    batch.updated_at = datetime.now(UTC)
    extraction_path(batch.extraction_id).write_text(batch.model_dump_json(indent=2), encoding="utf-8")


def load_extraction(extraction_id: str) -> ExtractionBatch:
    path = extraction_path(extraction_id)
    if not path.exists():
        raise FileNotFoundError(f"未找到核验批次 {extraction_id}")
    return ExtractionBatch.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _normalized_value(raw_value: float, raw_unit: str) -> float:
    multipliers = {"元": 1, "千元": 1_000, "万元": 10_000, "亿元": 100_000_000,
                   "基本单位": 1, "千单位": 1_000, "万单位": 10_000, "百万单位": 1_000_000, "亿单位": 100_000_000}
    if raw_unit not in multipliers:
        raise ValueError("单位仅支持基本、千、万、百万、亿单位，或元、千元、万元、亿元")
    return raw_value * multipliers[raw_unit]


def review_fact(extraction_id: str, fact_id: str, request: FactReviewRequest) -> ExtractionBatch:
    batch = load_extraction(extraction_id)
    fact = next((item for item in batch.facts if item.fact_id == fact_id), None)
    if fact is None:
        raise FileNotFoundError(f"未找到财务事实 {fact_id}")

    previous_value = fact.raw_value
    previous_unit = fact.raw_unit
    if request.action == "mark_missing":
        if not (request.reason or "").strip():
            raise ValueError("标记暂缺时必须填写原因")
        fact.value = None
        fact.raw_value = None
        fact.verification_status = VerificationStatus.MISSING
    else:
        raw_value = request.value if request.value is not None else fact.raw_value
        raw_unit = request.raw_unit or fact.raw_unit
        if raw_value is None:
            raise ValueError("确认数据前必须填写数值")
        if fact.raw_value is None and (request.page_number or fact.page_number) <= 0:
            raise ValueError("手动补充数值时必须填写原始 PDF 页码")
        if fact.raw_value is None and not (request.source_text or fact.source_text).strip():
            raise ValueError("手动补充数值时必须填写原文摘录")
        changed = raw_value != previous_value or raw_unit != previous_unit
        if changed and not (request.reason or "").strip():
            raise ValueError("修改数值或单位时必须填写原因")
        fact.raw_value = raw_value
        fact.raw_unit = raw_unit
        fact.value = _normalized_value(raw_value, raw_unit)
        fact.verification_status = VerificationStatus.VERIFIED

    if request.page_number is not None:
        fact.page_number = request.page_number
    if request.source_text is not None:
        fact.source_text = request.source_text
    fact.review_note = request.reason
    fact.reviewed_at = datetime.now(UTC)
    if fact.raw_value != previous_value or fact.raw_unit != previous_unit:
        fact.revisions.append(
            FactRevision(
                previous_value=previous_value,
                new_value=fact.raw_value,
                previous_unit=previous_unit,
                new_unit=fact.raw_unit,
                reason=request.reason or "人工核验",
            )
        )

    unresolved = [item for item in batch.facts if item.verification_status not in {VerificationStatus.VERIFIED, VerificationStatus.MISSING}]
    batch.status = ExtractionStatus.READY if not unresolved else ExtractionStatus.REVIEW_REQUIRED
    save_extraction(batch)
    return batch
