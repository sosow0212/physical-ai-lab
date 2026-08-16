"""실시간 텔레메트리 & 조기 이상 탐지 DTO."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ScenarioType(StrEnum):
    NORMAL = "NORMAL"
    ANOMALY_40 = "ANOMALY_40"
    ANOMALY_70 = "ANOMALY_70"
    CRITICAL_SPIKE = "CRITICAL_SPIKE"
    DRIFT = "DRIFT"


class CircuitState(StrEnum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    TRIP = "TRIP"


class TelemetryMessage(BaseModel):
    timestamp: datetime
    line_id: str = "LINE-1"
    equipment_id: str
    sensor_id: str
    metric_name: str
    value: float
    unit: str
    status: str = "NORMAL"


class GeneratorStatus(BaseModel):
    is_running: bool
    hz: int
    scenario: ScenarioType
    total_emitted: int
    started_at: datetime | None = None


class GeneratorScenarioIn(BaseModel):
    scenario: ScenarioType = ScenarioType.NORMAL
    hz: int | None = Field(default=None, ge=1, le=50)


class CircuitBreakerStatus(BaseModel):
    equipment_id: str
    equipment_name: str
    sensor_id: str
    metric_name: str
    state: CircuitState
    current_value: float
    z_score: float
    slope: float
    unit: str
    threshold_warning: float | None = None  # 자동 등록 설비는 미등록(통계 전용)
    threshold_trip: float | None = None
    source: str = "graph"  # graph | default | auto
    recent_values: list[float] = []
    updated_at: datetime


class EarlyWarningAlert(BaseModel):
    alert_id: str
    timestamp: datetime
    severity: str  # "WARNING" | "CRITICAL"
    equipment_id: str
    equipment_name: str
    sensor_id: str
    metric_name: str
    value: float
    unit: str
    reason: str
    z_score: float
    impact_path: list[str] = []
    guide_summary: str | None = None
    details: dict[str, Any] = {}
