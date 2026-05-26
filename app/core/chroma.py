import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings


def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(
        path=settings.CHROMA_PATH,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

