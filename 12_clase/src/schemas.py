"""HTTP request/response contracts (PRD section 5)."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    session_id: str
    response: str
    routing_used: str | None
    guardrail_status: Literal["passed", "blocked_input", "blocked_output"]
