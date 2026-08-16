"""실시간 텔레메트리 & 조기 경보 API — 제너레이터 제어, 서킷브레이커, SSE 스트림."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_anomaly_detector, get_telemetry_generator
from app.core.errors import NotFoundError
from app.schemas.telemetry import (
    CircuitBreakerStatus,
    EarlyWarningAlert,
    GeneratorScenarioIn,
    GeneratorStatus,
    ScenarioType,
)
from app.services.anomaly_detector import AnomalyDetector
from app.services.telemetry_service import TelemetryGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post("/generator/start", response_model=GeneratorStatus)
async def start_generator(
    gen: Annotated[TelemetryGenerator, Depends(get_telemetry_generator)],
    hz: int = Query(5, ge=1, le=50),
    scenario: ScenarioType = ScenarioType.NORMAL,
) -> GeneratorStatus:
    """텔레메트리 모의 데이터 생성 시작 (초당 hz 건, 시나리오 지정)."""
    return gen.start(hz=hz, scenario=scenario)


@router.post("/generator/stop", response_model=GeneratorStatus)
async def stop_generator(
    gen: Annotated[TelemetryGenerator, Depends(get_telemetry_generator)],
) -> GeneratorStatus:
    """텔레메트리 모의 데이터 생성 정지."""
    return gen.stop()


@router.post("/generator/scenario", response_model=GeneratorStatus)
async def set_scenario(
    body: GeneratorScenarioIn,
    gen: Annotated[TelemetryGenerator, Depends(get_telemetry_generator)],
) -> GeneratorStatus:
    """시뮬레이션 시나리오 변경 (NORMAL / ANOMALY_40 / ANOMALY_70 / CRITICAL_SPIKE / DRIFT)."""
    if not gen.status.is_running:
        gen.start(hz=body.hz or 5, scenario=body.scenario)
    else:
        gen.set_scenario(body.scenario, body.hz)
    return gen.status


@router.get("/generator/status", response_model=GeneratorStatus)
async def get_generator_status(
    gen: Annotated[TelemetryGenerator, Depends(get_telemetry_generator)],
) -> GeneratorStatus:
    """제너레이터 현재 가동 상태 및 통계."""
    return gen.status


@router.get("/circuit-breakers", response_model=list[CircuitBreakerStatus])
async def get_circuit_breakers(
    detector: Annotated[AnomalyDetector, Depends(get_anomaly_detector)],
) -> list[CircuitBreakerStatus]:
    """공정별 서킷 브레이커 현재 상태 (NORMAL / WARNING / TRIP)."""
    return detector.get_circuit_breakers()


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(
    detector: Annotated[AnomalyDetector, Depends(get_anomaly_detector)],
    equipment_id: str | None = Query(None),
) -> dict[str, str]:
    """서킷 브레이커 리셋 (NORMAL 복귀). 모르는 equipment_id는 404."""
    try:
        targets = detector.reset_circuit_breaker(equipment_id)
    except NotFoundError as exc:
        raise NotFoundError(exc.message) from exc
    return {"status": "ok", "message": f"Circuit breaker reset: {', '.join(targets)}"}


@router.post("/registry/reload")
async def reload_registry(
    detector: Annotated[AnomalyDetector, Depends(get_anomaly_detector)],
    gen: Annotated[TelemetryGenerator, Depends(get_telemetry_generator)],
) -> dict:
    """감시 대상 재로드 — 그래프에 설비/센서 추가 후 호출하면 즉시 반영."""
    result = await detector.reload_registry()
    await gen.refresh_profiles()
    return result


@router.get("/alerts", response_model=list[EarlyWarningAlert])
async def get_alerts(
    detector: Annotated[AnomalyDetector, Depends(get_anomaly_detector)],
    limit: int = Query(30, ge=1, le=100),
) -> list[EarlyWarningAlert]:
    """최근 발생한 조기 경보 내역 조회."""
    return detector.get_alerts(limit=limit)


@router.get("/stream")
async def stream_telemetry(
    request: Request,
    detector: Annotated[AnomalyDetector, Depends(get_anomaly_detector)],
) -> StreamingResponse:
    """SSE 실시간 텔레메트리, 서킷브레이커 및 조기 경보 스트림."""
    queue = detector.subscribe()

    async def event_generator() -> AsyncIterator[str]:
        try:
            # 최초 연결 시 초기 서킷 브레이커 상태 전송
            init_cbs = [cb.model_dump(mode="json") for cb in detector.get_circuit_breakers()]
            init_payload = json.dumps({"circuit_breakers": init_cbs}, ensure_ascii=False)
            yield f"event: init\ndata: {init_payload}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    evt_type = event.get("event", "telemetry")
                    payload = json.dumps(event.get("data", {}), ensure_ascii=False)
                    yield f"event: {evt_type}\ndata: {payload}\n\n"
                except TimeoutError:
                    # Keep-alive ping
                    yield ": ping\n\n"
        finally:
            detector.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
