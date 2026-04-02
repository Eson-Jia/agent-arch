from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Position(BaseModel):
    x: float
    y: float
    z: float
    map_ver: str


class Motion(BaseModel):
    speed_mps: float = Field(ge=0)
    heading_deg: float = Field(ge=0, le=360)
    mode: Literal["AUTO", "MANUAL", "ASSISTED"] = "AUTO"


class LoadState(BaseModel):
    state: Literal["EMPTY", "LOADED", "UNKNOWN"] = "UNKNOWN"
    payload_t: float = Field(default=0, ge=0)


class HealthState(BaseModel):
    fault_code: str | None = None
    soc_pct: float = Field(ge=0, le=100)
    engine_temp_c: float = Field(ge=0)


class CommsState(BaseModel):
    rssi_dbm: float
    uplink_kbps: float = Field(ge=0)
    loss_pct_5s: float = Field(ge=0, le=100)


class VehicleTelemetry(BaseModel):
    ts: datetime
    truck_id: str
    pos: Position
    motion: Motion
    load: LoadState
    health: HealthState
    comms: CommsState
    model_config = ConfigDict(extra="forbid")
