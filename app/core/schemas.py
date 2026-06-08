from pydantic import BaseModel, Field, field_validator

from app.core.config import settings


class ChatRequest(BaseModel):
    session_id: str | None = None
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=settings.CHAT_MAX_MESSAGE_CHARS)
    answer_style: str = 'detailed'

    @field_validator('message')
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('Message must not be empty.')
        return cleaned


class SourceItem(BaseModel):
    doc_id: str
    product: str
    brand: str
    category: str
    section: str
    source_file: str
    score: float = 0.0


class DocumentItem(BaseModel):
    title: str
    type: str
    product: str
    brand: str
    public_url: str


class ChatResponse(BaseModel):
    session_id: str
    conversation_id: str
    request_id: str
    answer: str
    original_query: str
    resolved_query: str
    depends_on_history: bool = False
    answer_mode: str
    sources: list[SourceItem] = Field(default_factory=list)
    documents: list[DocumentItem] = Field(default_factory=list)
    used_web_search: bool = False
    web_results: list[dict] = Field(default_factory=list)
    confidence: str = 'low'
    tools_used: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    request_id: str
    rating: str
    comment: str = ''
