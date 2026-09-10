from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec

from bcra_rag.adapters.index_chroma import ChromaIndex
from bcra_rag.adapters.llm_fake import UnavailableLlm
from bcra_rag.adapters.llm_openai import LlmAdapter
from bcra_rag.adapters.otel import build_tracer
from bcra_rag.adapters.policy_yaml import default_policy_path, load_policy
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.domain.guardrails.registry import assemble_pipeline
from bcra_rag.domain.guardrails.types import Tracer
from bcra_rag.evals.adapters.sink_noop import NoOpEvalSink
from bcra_rag.evals.ports.judge import Judge
from bcra_rag.evals.ports.sink import EvalSink
from bcra_rag.evals.settings import EvalSettings
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.settings import Settings


@dataclass(frozen=True)
class EvalsApp:
    settings: Settings
    eval_settings: EvalSettings
    index: IndexPort
    llm: LlmPort
    pipeline: GuardrailPipeline
    judge: Judge | None
    judge_skip_reason: str | None
    sink: EvalSink
    tracer: Tracer


def build_evals(
    settings: Settings | None = None,
    eval_settings: EvalSettings | None = None,
    *,
    index: IndexPort | None = None,
    llm: LlmPort | None = None,
    pipeline: GuardrailPipeline | None = None,
    judge: Judge | None = None,
    sink: EvalSink | None = None,
    tracer: Tracer | None = None,
) -> EvalsApp:
    resolved = settings or Settings()
    resolved_eval = eval_settings or EvalSettings()
    resolved_index = index or ChromaIndex(resolved)
    resolved_llm = llm or (
        LlmAdapter(resolved) if resolved.llm_api_key else UnavailableLlm()
    )
    resolved_tracer = tracer or build_tracer(
        resolved,
        endpoint=resolved_eval.phoenix_collector_endpoint,
        api_key=resolved_eval.phoenix_api_key,
        project_name=resolved_eval.phoenix_project_name,
    )
    resolved_pipeline = pipeline or assemble_pipeline(
        load_policy(resolved.guardrails_policy_path or default_policy_path()),
        resolved,
        resolved_tracer,
    )
    resolved_judge: Judge | None
    judge_skip_reason: str | None
    if judge is not None:
        resolved_judge = judge
        judge_skip_reason = None
    else:
        resolved_judge, judge_skip_reason = _maybe_judge(resolved_eval)
    resolved_sink = sink or _maybe_sink(resolved_eval)
    return EvalsApp(
        settings=resolved,
        eval_settings=resolved_eval,
        index=resolved_index,
        llm=resolved_llm,
        pipeline=resolved_pipeline,
        judge=resolved_judge,
        judge_skip_reason=judge_skip_reason,
        sink=resolved_sink,
        tracer=resolved_tracer,
    )


def _maybe_judge(eval_settings: EvalSettings) -> tuple[Judge | None, str | None]:
    if not eval_settings.resolved_judge_key():
        return None, "no_judge"
    try:
        if find_spec("phoenix.evals") is None:
            return None, "missing_extra"
        from bcra_rag.evals.adapters.judge_phoenix import PhoenixJudge

        return PhoenixJudge(eval_settings), None
    except Exception:
        return None, "missing_extra"


def _maybe_sink(eval_settings: EvalSettings) -> EvalSink:
    endpoint = (eval_settings.phoenix_collector_endpoint or "").strip()
    if not endpoint:
        return NoOpEvalSink()
    try:
        from bcra_rag.evals.adapters.sink_phoenix import PhoenixEvalSink

        return PhoenixEvalSink(
            endpoint,
            eval_settings.phoenix_project_name,
            api_key=eval_settings.phoenix_api_key,
        )
    except Exception:
        return NoOpEvalSink()
