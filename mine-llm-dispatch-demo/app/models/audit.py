from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    event_id: str
    ts: datetime
    event_type: str
    actor: str
    evidence: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(extra="forbid")
