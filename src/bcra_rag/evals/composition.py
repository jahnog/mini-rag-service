from __future__ import annotations

from dataclasses import dataclass

from bcra_rag.adapters.index_chroma import ChromaIndex
from bcra_rag.adapters.llm_fake import UnavailableLlm
from bcra_rag.adapters.llm_openai import LlmAdapter
from bcra_rag.adapters.policy_yaml import default_policy_path, load_policy
from bcra_rag.domain.guardrails import GuardrailPipeline
from bcra_rag.domain.guardrails.registry import assemble_pipeline
from bcra_rag.ports.index import IndexPort
from bcra_rag.ports.llm import LlmPort
from bcra_rag.settings import Settings


@dataclass(frozen=True)
class EvalsApp:
    settings: Settings
    index: IndexPort
    llm: LlmPort
    pipeline: GuardrailPipeline


def build_evals(
    settings: Settings | None = None,
    *,
    index: IndexPort | None = None,
    llm: LlmPort | None = None,
    pipeline: GuardrailPipeline | None = None,
) -> EvalsApp:
    resolved = settings or Settings()
    return EvalsApp(
        settings=resolved,
        index=index or ChromaIndex(resolved),
        llm=llm or (LlmAdapter(resolved) if resolved.llm_api_key else UnavailableLlm()),
        pipeline=pipeline
        or assemble_pipeline(
            load_policy(resolved.guardrails_policy_path or default_policy_path()),
            resolved,
        ),
    )
