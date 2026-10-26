"""HTTP request/response contracts (PRD section 5)."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.evaluation import DATASET_NAME, DEFAULT_METRICS, MAX_METRICS, Metric


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    session_id: str
    response: str
    routing_used: str | None
    guardrail_status: Literal["passed", "blocked_input", "blocked_output"]


class EvalRequest(BaseModel):
    dataset_name: str = Field(pattern=DATASET_NAME)
    metrics: list[Metric] = Field(
        default_factory=lambda: list(DEFAULT_METRICS), min_length=1, max_length=MAX_METRICS
    )

    @field_validator("metrics")
    @classmethod
    def no_duplicates(cls, metrics: list[Metric]) -> list[Metric]:
        if len(set(metrics)) != len(metrics):
            raise ValueError("metrics must not repeat")
        return metrics


class EvalResponse(BaseModel):
    status: Literal["completed"] = "completed"
    samples_evaluated: int
    scores: dict[str, float | None]
    timestamp: str
