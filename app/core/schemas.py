from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    answer_style: str = 'detailed'


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
