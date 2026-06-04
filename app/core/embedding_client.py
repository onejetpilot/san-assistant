import httpx

from app.core.config import settings


class EmbeddingNotConfiguredError(RuntimeError):
    pass


class EmbeddingClient:
    @staticmethod
    def _iter_batches(texts: list[str]) -> list[list[str]]:
        batch_size = max(int(settings.EMBEDDING_BATCH_SIZE or 1), 1)
        return [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]

    @staticmethod
    def is_configured() -> bool:
        return (
            settings.EMBEDDING_PROVIDER == 'openai_compatible'
            and bool(settings.EMBEDDING_API_KEY)
            and bool(settings.EMBEDDING_BASE_URL)
        )

    @classmethod
    def _ensure_configured(cls) -> None:
        if not cls.is_configured():
            raise EmbeddingNotConfiguredError('Embedding provider is not configured')

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self._ensure_configured()
        if not texts:
            return []

        vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            for batch in self._iter_batches(texts):
                resp = await client.post(
                    f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
                    headers={'Authorization': f'Bearer {settings.EMBEDDING_API_KEY}'},
                    json={'model': settings.EMBEDDING_MODEL, 'input': batch},
                )
                resp.raise_for_status()
                vectors.extend(item['embedding'] for item in resp.json()['data'])
        return vectors

    def embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        self._ensure_configured()
        if not texts:
            return []

        vectors: list[list[float]] = []
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            for batch in self._iter_batches(texts):
                resp = client.post(
                    f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
                    headers={'Authorization': f'Bearer {settings.EMBEDDING_API_KEY}'},
                    json={'model': settings.EMBEDDING_MODEL, 'input': batch},
                )
                resp.raise_for_status()
                vectors.extend(item['embedding'] for item in resp.json()['data'])
        return vectors
