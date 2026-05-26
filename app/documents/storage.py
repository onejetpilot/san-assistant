from app.core.config import settings


class DocumentStorageProvider:
    def resolve_public_url(self, metadata: dict) -> str:
        raise NotImplementedError


class GitHubRawStorageProvider(DocumentStorageProvider):
    def resolve_public_url(self, metadata: dict) -> str:
        return metadata.get('public_url', '')


class S3StorageProvider(DocumentStorageProvider):
    def resolve_public_url(self, metadata: dict) -> str:
        return metadata.get('public_url', '')


def get_storage_provider() -> DocumentStorageProvider:
    provider = getattr(settings, 'DOCUMENT_STORAGE_PROVIDER', 'github')
    if provider == 's3':
        return S3StorageProvider()
    return GitHubRawStorageProvider()
