from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AlarmLevel = Literal["RED", "ORANGE", "YELLOW", "BLUE"]


class AlarmLocation(BaseModel):
    road_segment: str
    bbox: list[float] = Field(default_factory=list)


class ImpactZone(BaseModel):
    blocked: bool = False
    detour_routes: list[str] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    type: str
    id: str
    confidence: float = Field(ge=0, le=1)


class SafetyAlarmEvent(BaseModel):
    source_event_id: str | None = None
    alarm_id: str
    ts: datetime
    level: AlarmLevel
    category: str
    location: AlarmLocation
    impact_zone: ImpactZone = Field(default_factory=ImpactZone)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")
