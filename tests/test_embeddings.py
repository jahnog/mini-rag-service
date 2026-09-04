from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from bcra_rag.adapters.embeddings import (
    DeterministicEmbeddingFunction,
    OpenAICompatibleEmbeddingFunction,
    resolve_embedding_function,
)
from bcra_rag.settings import Settings


@dataclass
class _Item:
    index: int
    embedding: list[float]


@dataclass
class _Response:
    data: list[_Item]


class FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.fail_if_batch_gt: int | None = None

    def create(self, **kwargs):  # type: ignore[no-untyped-def]
        batch = list(kwargs["input"])
        self.calls.append(batch)
        if self.fail_if_batch_gt is not None and len(batch) > self.fail_if_batch_gt:
            raise RuntimeError("batch too large")
        return _Response(
            [_Item(index=i, embedding=[float(i + 1), 0.0]) for i, _ in enumerate(batch)]
        )


class FakeClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddingsAPI()


def test_openai_compatible_embeds_in_batches() -> None:
    client = FakeClient()
    ef = OpenAICompatibleEmbeddingFunction(
        api_key="sk-test",
        api_base="http://example.invalid/v1",
        model_name="qwen3-embedding-0.6b",
        batch_size=2,
        client=client,
    )
    vectors = ef(["a", "b", "c", "d", "e"])
    assert len(vectors) == 5
    assert [call[0] for call in client.embeddings.calls] == ["a", "c", "e"]
    assert [len(call) for call in client.embeddings.calls] == [2, 2, 1]
    assert vectors[0][0] == 1.0


def test_openai_compatible_default_clips_at_2048() -> None:
    client = FakeClient()
    ef = OpenAICompatibleEmbeddingFunction(
        api_key="sk-test",
        api_base="http://example.invalid/v1",
        model_name="qwen3-embedding-0.6b",
        client=client,
    )
    ef(["x" * 3000])
    assert len(client.embeddings.calls[0][0]) == 2048


def test_openai_compatible_clips_long_input() -> None:
    client = FakeClient()
    ef = OpenAICompatibleEmbeddingFunction(
        api_key="sk-test",
        api_base="http://example.invalid/v1",
        model_name="qwen3-embedding-0.6b",
        batch_size=8,
        max_chars=10,
        client=client,
    )
    ef(["abcdefghijklmnop"])
    assert client.embeddings.calls == [["abcdefghij"]]


def test_openai_compatible_retries_single_oversized_item() -> None:
    client = FakeClient()
    original_create = client.embeddings.create

    def create(**kwargs):  # type: ignore[no-untyped-def]
        batch = list(kwargs["input"])
        if len(batch[0]) > 400:
            client.embeddings.calls.append(batch)
            raise RuntimeError("ctx")
        return original_create(**kwargs)

    client.embeddings.create = create  # type: ignore[method-assign]
    ef = OpenAICompatibleEmbeddingFunction(
        api_key="sk-test",
        api_base="http://example.invalid/v1",
        model_name="qwen3-embedding-0.6b",
        max_chars=8000,
        client=client,
    )
    vectors = ef(["x" * 500])
    assert len(vectors) == 1
    assert len(client.embeddings.calls[-1][0]) <= 256


def test_openai_compatible_splits_failed_batch() -> None:
    client = FakeClient()
    client.embeddings.fail_if_batch_gt = 1
    ef = OpenAICompatibleEmbeddingFunction(
        api_key="sk-test",
        api_base="http://example.invalid/v1",
        model_name="qwen3-embedding-0.6b",
        batch_size=4,
        client=client,
    )
    vectors = ef(["one", "two"])
    assert len(vectors) == 2
    assert ["one"] in client.embeddings.calls
    assert ["two"] in client.embeddings.calls


def test_resolve_auto_without_key_is_deterministic(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, embedding_api_key="")
    ef = resolve_embedding_function(settings)
    assert isinstance(ef, DeterministicEmbeddingFunction)


def test_resolve_auto_with_key_is_openai_compatible(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        embedding_api_key="sk-test",
        embedding_batch_size=4,
    )
    ef = resolve_embedding_function(settings)
    assert isinstance(ef, OpenAICompatibleEmbeddingFunction)
    assert ef.get_config()["batch_size"] == 4


def test_resolve_onnx_uses_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(data_dir=tmp_path, embedding_backend="onnx")

    def fake_onnx() -> str:
        return "onnx-ef"

    monkeypatch.setattr("bcra_rag.adapters.embeddings._onnx_embedding_function", fake_onnx)
    assert resolve_embedding_function(settings) == "onnx-ef"


def test_resolve_openai_without_key_raises(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path, embedding_backend="openai", embedding_api_key=""
    )
    with pytest.raises(ValueError, match="EMBEDDING_API_KEY"):
        resolve_embedding_function(settings)


def test_resolve_override_wins(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, embedding_api_key="sk-test")
    override = DeterministicEmbeddingFunction(dim=3)
    assert resolve_embedding_function(settings, override) is override


def test_resolve_deterministic_backend_ignores_key(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        embedding_backend="deterministic",
        embedding_api_key="sk-test",
    )
    assert isinstance(
        resolve_embedding_function(settings), DeterministicEmbeddingFunction
    )


def test_resolve_unknown_backend_without_key_is_deterministic(tmp_path: Path) -> None:
    settings = Settings(
        data_dir=tmp_path, embedding_backend="nope", embedding_api_key=""
    )
    assert isinstance(
        resolve_embedding_function(settings), DeterministicEmbeddingFunction
    )
