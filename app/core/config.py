from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    ROUTERAI_API_KEY: str = ''
    ROUTERAI_BASE_URL: str = 'https://routerai.ru/api/v1'
    LLM_MODEL: str = 'openai/gpt-4o-mini'
    LLM_TEMPERATURE: float = 0.2
    LLM_TIMEOUT_SECONDS: int = 60

    EMBEDDING_PROVIDER: str = 'openai_compatible'
    EMBEDDING_API_KEY: str = ''
    EMBEDDING_BASE_URL: str = ''
    EMBEDDING_MODEL: str = 'text-embedding-3-small'
    EMBEDDING_BATCH_SIZE: int = 64

    CHROMA_PATH: str = './data/chroma'
    CHROMA_COLLECTION_PRODUCT_CHUNKS: str = 'product_chunks'
    CHROMA_COLLECTION_PRODUCT_CARDS: str = 'product_cards'
    CHROMA_COLLECTION_DOCUMENTS: str = 'documents'

    KNOWLEDGE_BASE_PATH: str = '/kb/knowledge_base'
    DOCUMENTS_REPO_PATH: str = '/docs'
    DOCUMENTS_METADATA_PATH: str = '/docs/metadata/documents.yml'
    DOCUMENT_STORAGE_PROVIDER: str = 'github'

    TOP_K: int = 8
    RERANK_TOP_K: int = 5
    ENABLE_RERANKER: bool = False

    ROUTER_MODE: str = 'hybrid'
    ENABLE_WEB_SEARCH: bool = True
    WEB_SEARCH_PROVIDER: str = ''
    WEB_SEARCH_API_KEY: str = ''

    ENABLE_ANSWER_EVALUATION: bool = False
    JUDGE_MODEL: str = 'google/gemini-2.5-flash'

    DATABASE_URL: str = 'sqlite:///./data/app.db'
    ADMIN_ENABLED: bool = True


settings = Settings()
