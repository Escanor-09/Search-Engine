# Pydantic response models for every endpoint -- gives FastAPI's response_model
# validation + auto-generated OpenAPI docs instead of hand-shaped dicts.
from typing import Optional
from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    doc_id: int
    title: str
    company: Optional[str] = None
    url: Optional[str] = None
    score: float
    snippet: str


# the normal, successful /search shape: a ranked, paginated result set
class SearchResponse(BaseModel):
    query: str
    page: int
    page_size: int
    total_results: int
    total_pages: int
    results: list[SearchResultItem]
    # only present when spellcheck actually corrected something
    did_you_mean: Optional[str] = None


# covers both zero-result branches in main.py: unknown-word rejections
# (unknown_words populated) and "no searchable terms" queries (message only)
class NoResultsResponse(BaseModel):
    query: str
    message: str
    unknown_words: list[str] = Field(default_factory=list)
    results: list[SearchResultItem] = Field(default_factory=list)


class SuggestResponse(BaseModel):
    prefix: str
    suggestions: list[str]


class HealthResponse(BaseModel):
    status: str
    corpus_size: int
    uptime_seconds: float
    started_at: str


class ErrorResponse(BaseModel):
    detail: str
