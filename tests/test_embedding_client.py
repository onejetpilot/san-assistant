from types import SimpleNamespace

import app.core.embedding_client as embedding_module
from app.core.embedding_client import EmbeddingClient


class _FakeResponse:
    def __init__(self, batch: list[str]):
        self._batch = batch

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            'data': [
                {'embedding': [float(index), float(len(text))]}
                for index, text in enumerate(self._batch, start=1)
            ],
        }


class _FakeClient:
    def __init__(self, recorder: list[list[str]]):
        self._recorder = recorder

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url: str, headers: dict, json: dict):
        batch = list(json['input'])
        self._recorder.append(batch)
        return _FakeResponse(batch)


def test_embed_texts_sync_batches_requests(monkeypatch):
    batches: list[list[str]] = []

    monkeypatch.setattr(
        embedding_module,
        'settings',
        SimpleNamespace(
            EMBEDDING_PROVIDER='openai_compatible',
            EMBEDDING_API_KEY='secret',
            EMBEDDING_BASE_URL='https://example.test/v1',
            EMBEDDING_MODEL='embedding-test',
            EMBEDDING_BATCH_SIZE=2,
            LLM_TIMEOUT_SECONDS=5,
        ),
    )
    monkeypatch.setattr(embedding_module.httpx, 'Client', lambda timeout: _FakeClient(batches))

    vectors = EmbeddingClient().embed_texts_sync(['one', 'two', 'three', 'four', 'five'])

    assert batches == [['one', 'two'], ['three', 'four'], ['five']]
    assert vectors == [
        [1.0, 3.0],
        [2.0, 3.0],
        [1.0, 5.0],
        [2.0, 4.0],
        [1.0, 4.0],
    ]


def test_embed_texts_sync_returns_empty_without_requests(monkeypatch):
    monkeypatch.setattr(
        embedding_module,
        'settings',
        SimpleNamespace(
            EMBEDDING_PROVIDER='openai_compatible',
            EMBEDDING_API_KEY='secret',
            EMBEDDING_BASE_URL='https://example.test/v1',
            EMBEDDING_MODEL='embedding-test',
            EMBEDDING_BATCH_SIZE=2,
            LLM_TIMEOUT_SECONDS=5,
        ),
    )

    calls: list[list[str]] = []
    monkeypatch.setattr(embedding_module.httpx, 'Client', lambda timeout: _FakeClient(calls))

    assert EmbeddingClient().embed_texts_sync([]) == []
    assert calls == []
