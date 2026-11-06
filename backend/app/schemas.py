from typing import Any, Literal
from pydantic import BaseModel

Mode = Literal["auto", "classical", "deep", "hybrid"]


class ResultRecord(BaseModel):
    id: str
    kind: str
    created_at: str
    requested_mode: str
    executed_mode: str
    latency_ms: float
    image: dict[str, Any]
    analysis: dict[str, Any]
    artifacts: dict[str, str]
    metrics: dict[str, Any] = {}
    diagnostics: list[dict[str, Any]] = []
    parameters: dict[str, Any] = {}
    comparisons: dict[str, Any] = {}
    controller: dict[str, Any] | None = None
    notices: list[str] = []
