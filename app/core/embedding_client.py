import httpx

from app.core.config import settings


class EmbeddingNotConfiguredError(RuntimeError):
    pass


class EmbeddingClient:
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
        async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
                headers={'Authorization': f'Bearer {settings.EMBEDDING_API_KEY}'},
                json={'model': settings.EMBEDDING_MODEL, 'input': texts},
            )
            resp.raise_for_status()
            return [item['embedding'] for item in resp.json()['data']]

    def embed_texts_sync(self, texts: list[str]) -> list[list[float]]:
        self._ensure_configured()
        with httpx.Client(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
            resp = client.post(
                f"{settings.EMBEDDING_BASE_URL.rstrip('/')}/embeddings",
                headers={'Authorization': f'Bearer {settings.EMBEDDING_API_KEY}'},
                json={'model': settings.EMBEDDING_MODEL, 'input': texts},
            )
            resp.raise_for_status()
            return [item['embedding'] for item in resp.json()['data']]
