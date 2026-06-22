from pydantic import BaseModel

class SearchSubmission(BaseModel):
    query: str

class SuggestionResult(BaseModel):
    query: str
    count: int

class SearchResponse(BaseModel):
    message: str

class DebugResponse(BaseModel):
    node: str
    is_hit: bool
