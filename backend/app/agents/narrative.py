from __future__ import annotations

import json
import os
from pathlib import Path

from app.config import OPENAI_MODEL
from app.models.contracts import AnomalySignal, FinancialFact, MetricCalculation
from app.tools.audit import append_tool_log


class NarrativeGenerationError(RuntimeError):
    """Raised when the optional GPT narrative cannot be produced."""


def generate_verified_narrative(run_dir: Path, facts: list[FinancialFact], calculations: list[MetricCalculation], signals: list[AnomalySignal]) -> str | None:
    """Use GPT only for prose; every provided fact is already extracted and logged."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from openai import OpenAI, OpenAIError

    evidence = {
        "facts": [item.model_dump(mode="json") for item in facts],
        "calculations": [item.model_dump(mode="json") for item in calculations],
        "signals": [item.model_dump(mode="json") for item in signals],
    }
    instructions = """你是审慎的中国上市公司财务分析师。仅使用提供的已验证事实、计算与风险信号。
用中文输出不超过 500 字的分析摘要。每段开头用 [F]、[I] 或 [R] 标识事实、推论或风险。
不得自行补充数字、原因或结论；不得认定财务造假；风险结论必须使用审慎措辞。"""
    client = OpenAI()
    try:
        response = client.responses.create(model=OPENAI_MODEL, instructions=instructions, input=json.dumps(evidence, ensure_ascii=False))
    except OpenAIError as error:
        raise NarrativeGenerationError(str(error)) from error
    append_tool_log(run_dir, "openai.responses.create", {"model": OPENAI_MODEL, "request_id": getattr(response, "_request_id", None)})
    return response.output_text

