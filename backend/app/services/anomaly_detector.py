"""실시간 이상 탐지기 & 공정 서킷 브레이커 — 슬라이딩 윈도우 + GraphRAG/RAG 연계.

감시 대상은 MonitorRegistry(Neo4j 그래프 SSOT)에서 로드한다.
- 그래프에 센서를 추가하면 registry reload(/telemetry/registry/reload)로 즉시 반영
- 그래프에 없는 설비의 텔레메트리가 오면 자동 등록(통계 전용 감시) + 그래프 노드 생성
"""

import asyncio
import contextlib
import json
import logging
import math
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaConsumer
from motor.motor_asyncio import AsyncIOMotorDatabase
from neo4j import AsyncDriver
from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.infrastructure.milvus import search_manual_chunks
from app.repositories.neo4j.graph_repository import GraphRepository
from app.schemas.telemetry import (
    CircuitBreakerStatus,
    CircuitState,
    EarlyWarningAlert,
)
from app.services.embedding_service import embed_texts
from app.services.monitor_registry import MonitorProfile, MonitorRegistry

logger = logging.getLogger(__name__)

TOPIC_TELEMETRY = "telemetry.line1"
WINDOW_SIZE = 30
ALERTS_COLLECTION = "early_warning_alerts"

#: 통계 전용(자동 등록) 설비의 Z-score 임계
STAT_ONLY_WARNING_Z = 3.0
STAT_ONLY_TRIP_Z = 5.0


def _breaker_from_profile(profile: MonitorProfile) -> dict[str, Any]:
    return {
        "equipment_id": profile.equipment_id,
        "equipment_name": profile.equipment_name,
        "sensor_id": profile.sensor_id,
        "metric_name": profile.metric_name,
        "state": CircuitState.NORMAL,
        "current_value": 0.0,
        "z_score": 0.0,
        "slope": 0.0,
        "unit": profile.unit,
        "threshold_warning": profile.warning_threshold,
        "threshold_trip": profile.trip_threshold,
        "is_lower_limit": profile.is_lower_limit,
        "source": profile.source,  # graph | default | auto
        "recent_values": [],
        "updated_at": datetime.now(UTC),
    }


class AnomalyDetector:
    def __init__(
        self,
        settings: Settings,
        neo4j_driver: AsyncDriver | None = None,
        milvus_client: MilvusClient | None = None,
        redis_client: Redis | None = None,
        mongo_db: AsyncIOMotorDatabase | None = None,
    ) -> None:
        self._settings = settings
        self._graph_repo = GraphRepository(neo4j_driver) if neo4j_driver else None
        self._milvus = milvus_client
        self._redis = redis_client
        self._mongo = mongo_db

        self._registry = MonitorRegistry(self._graph_repo)

        # 설비별 센서 슬라이딩 윈도우: key = f"{equipment_id}:{sensor_id}"
        self._windows: dict[str, deque[float]] = {}
        self._timestamps: dict[str, deque[float]] = {}

        # 공정별 서킷 브레이커 상태: key = equipment_id
        self._circuit_breakers: dict[str, dict[str, Any]] = {}

        self._recent_alerts: deque[EarlyWarningAlert] = deque(maxlen=50)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

        self._consumer: AIOKafkaConsumer | None = None
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """레지스트리 로드 + 컨슈머 루프 시작."""
        if self._running:
            return
        await self.reload_registry()
        await self._load_alerts_from_mongo()
        self._running = True
        self._task = asyncio.create_task(self._run_consumer())
        logger.info(
            "이상 탐지 엔진 가동",
            extra={"topic": TOPIC_TELEMETRY, "monitors": len(self._circuit_breakers)},
        )

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
        if self._consumer:
            await self._consumer.stop()
        logger.info("이상 탐지 엔진 정지")

    async def reload_registry(self) -> dict[str, Any]:
        """그래프에서 모니터 프로파일 재로드. 동작 중 상태(전이/창)는 유지한다."""
        profiles = await self._registry.load()
        for eq_id, profile in profiles.items():
            if eq_id in self._circuit_breakers:
                # 임계치/이름 등만 갱신 (state, window 유지)
                cb = self._circuit_breakers[eq_id]
                cb.update(
                    {
                        "equipment_name": profile.equipment_name,
                        "sensor_id": profile.sensor_id,
                        "metric_name": profile.metric_name,
                        "unit": profile.unit,
                        "threshold_warning": profile.warning_threshold,
                        "threshold_trip": profile.trip_threshold,
                        "is_lower_limit": profile.is_lower_limit,
                        "source": profile.source,
                    }
                )
            else:
                self._circuit_breakers[eq_id] = _breaker_from_profile(profile)

        # 그래프에서 사라진 설비는 감시 목록에서도 제거 (창/브레이커 정리)
        removed = [eq for eq in self._circuit_breakers if eq not in profiles]
        for eq in removed:
            cb = self._circuit_breakers.pop(eq)
            self._windows.pop(f"{eq}:{cb['sensor_id']}", None)
            self._timestamps.pop(f"{eq}:{cb['sensor_id']}", None)
        if removed:
            logger.info("감시 목록에서 제거", extra={"removed": removed})
            self._broadcast({"event": "registry_changed", "data": {"removed": removed}})

        return {"monitors": len(self._circuit_breakers), "sources": self.sources_summary()}

    def sources_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for cb in self._circuit_breakers.values():
            summary[cb["source"]] = summary.get(cb["source"], 0) + 1
        return summary

    def get_circuit_breakers(self) -> list[CircuitBreakerStatus]:
        return [
            CircuitBreakerStatus(
                equipment_id=cb["equipment_id"],
                equipment_name=cb["equipment_name"],
                sensor_id=cb["sensor_id"],
                metric_name=cb["metric_name"],
                state=cb["state"],
                current_value=cb["current_value"],
                z_score=cb["z_score"],
                slope=cb["slope"],
                unit=cb["unit"],
                threshold_warning=cb["threshold_warning"],
                threshold_trip=cb["threshold_trip"],
                source=cb.get("source", "graph"),
                recent_values=cb.get("recent_values", [])[-20:],
                updated_at=cb["updated_at"],
            )
            for cb in self._circuit_breakers.values()
        ]

    def get_alerts(self, limit: int = 30) -> list[EarlyWarningAlert]:
        return list(self._recent_alerts)[-limit:]

    def reset_circuit_breaker(self, equipment_id: str | None = None) -> list[str]:
        """서킷 브레이커 리셋. 모르는 ID면 NotFoundError (전체 리셋 방지)."""
        if equipment_id is None:
            targets = list(self._circuit_breakers.keys())
        elif equipment_id in self._circuit_breakers:
            targets = [equipment_id]
        else:
            raise NotFoundError(f"감시 대상에 없는 설비입니다: {equipment_id}")

        for eq_id in targets:
            cb = self._circuit_breakers[eq_id]
            cb["state"] = CircuitState.NORMAL
            cb["z_score"] = 0.0
            cb["slope"] = 0.0
            cb["recent_values"] = []
            cb["updated_at"] = datetime.now(UTC)
            win_key = f"{eq_id}:{cb['sensor_id']}"
            self._windows.get(win_key, deque()).clear()
            self._timestamps.get(win_key, deque()).clear()
        logger.info("서킷 브레이커 리셋", extra={"targets": targets})
        self._broadcast({"event": "circuit_reset", "targets": targets})
        return targets

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(q)

    def _broadcast(self, event: dict[str, Any]) -> None:
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.discard(q)

    async def _run_consumer(self) -> None:
        """Kafka telemetry.line1 스트림 컨슘 & 실시간 분석 (끊기면 5초 후 재접속)."""
        while self._running:
            try:
                self._consumer = AIOKafkaConsumer(
                    TOPIC_TELEMETRY,
                    bootstrap_servers=self._settings.kafka_bootstrap,
                    group_id=f"{self._settings.kafka_group_id}-detector",
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                )
                await self._consumer.start()
                logger.info("이상 탐지 카프카 컨슈머 연결 완료")

                async for record in self._consumer:
                    if not self._running:
                        break
                    await self._process_sample(record.value)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning(
                    "이상 탐지 컨슈머 일시 오류 (5초 후 재접속)", extra={"error": str(exc)}
                )
                await asyncio.sleep(5)
            finally:
                if self._consumer:
                    with contextlib.suppress(Exception):
                        await self._consumer.stop()

    async def _process_sample(self, sample: dict[str, Any]) -> None:
        """텔레메트리 1건 처리: 미등록 설비면 자동 등록 → 창 갱신 → 서킷브레이커 전이."""
        eq_id = sample.get("equipment_id", "")
        sensor_id = sample.get("sensor_id", "")
        val = float(sample.get("value", 0.0))
        now_ts = datetime.now(UTC).timestamp()

        cb = self._circuit_breakers.get(eq_id)
        if cb is None:
            profile = await self._registry.get_or_auto_register(sample)
            if profile is None:
                return
            cb = _breaker_from_profile(profile)
            self._circuit_breakers[eq_id] = cb
            self._broadcast(
                {
                    "event": "monitor_registered",
                    "data": {
                        "equipment_id": eq_id,
                        "sensor_id": sensor_id,
                        "source": "auto",
                    },
                }
            )

        if not sensor_id:
            sensor_id = cb["sensor_id"]

        win_key = f"{eq_id}:{sensor_id}"
        if win_key not in self._windows:
            self._windows[win_key] = deque(maxlen=WINDOW_SIZE)
            self._timestamps[win_key] = deque(maxlen=WINDOW_SIZE)
        win = self._windows[win_key]
        ts_win = self._timestamps[win_key]
        win.append(val)
        ts_win.append(now_ts)

        # 1. 슬라이딩 윈도우 통계
        n = len(win)
        mean = sum(win) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in win) / n)
        z_score = abs(val - mean) / (std + 1e-4) if n >= 5 else 0.0

        # 변화율(slope): 초당 변화량으로 정규화 — 발송 주파수(hz)와 무관하게 동일 민감도
        slope_per_sec = 0.0
        if n >= 5:
            dt = ts_win[-1] - ts_win[0]
            if dt > 1e-6:
                slope_per_sec = (win[-1] - win[0]) / dt

        # 2. 상태 판정
        prev_state = cb["state"]
        new_state, reason = self._evaluate(cb, val, z_score, slope_per_sec)

        # TRIP은 수동 리셋 전까지 유지 (보호 논리)
        if prev_state == CircuitState.TRIP and new_state != CircuitState.TRIP:
            new_state = CircuitState.TRIP

        cb["current_value"] = val
        cb["z_score"] = round(z_score, 2)
        cb["slope"] = round(slope_per_sec, 4)
        cb["state"] = new_state
        cb["updated_at"] = datetime.now(UTC)
        cb.setdefault("recent_values", []).append(val)
        if len(cb["recent_values"]) > 30:
            cb["recent_values"] = cb["recent_values"][-30:]

        # 3. 상태 전이 시 지능형 알람 (GraphRAG 영향경로 + RAG 조치가이드)
        if new_state in (CircuitState.WARNING, CircuitState.TRIP) and prev_state != new_state:
            await self._trigger_early_warning_alert(
                eq_id=eq_id,
                cb=cb,
                sensor_id=sensor_id,
                value=val,
                severity=new_state.value,
                reason=reason,
                z_score=round(z_score, 2),
            )

        # 4. SSE 브로드캐스트
        self._broadcast(
            {
                "event": "telemetry",
                "data": {
                    "equipment_id": eq_id,
                    "equipment_name": cb["equipment_name"],
                    "sensor_id": sensor_id,
                    "metric_name": cb["metric_name"],
                    "value": val,
                    "unit": cb["unit"],
                    "z_score": cb["z_score"],
                    "slope": cb["slope"],
                    "state": new_state.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            }
        )

    @staticmethod
    def _evaluate(
        cb: dict[str, Any], val: float, z_score: float, slope_per_sec: float
    ) -> tuple[CircuitState, str]:
        """임계치 기반 상태 판정. 임계치 미등록(자동 등록) 설비는 통계 전용."""
        warn_th = cb.get("threshold_warning")
        trip_th = cb.get("threshold_trip")
        is_lower = cb.get("is_lower_limit", False)
        unit = cb["unit"]

        # 통계 전용 모드 (자동 등록 설비, 임계치 미정)
        if warn_th is None or trip_th is None:
            if z_score >= STAT_ONLY_TRIP_Z:
                return CircuitState.TRIP, f"통계적 급변 감지 (Z={z_score:.1f}, 임계치 미등록)"
            if z_score >= STAT_ONLY_WARNING_Z:
                return CircuitState.WARNING, f"통계적 이상 징후 (Z={z_score:.1f}, 임계치 미등록)"
            return CircuitState.NORMAL, ""

        # slope 민감도: (트립-주의) 임계폭의 1/10 을 초당 기준으로 (hz 무관)
        slope_warn = (trip_th - warn_th) / 10.0  # 하한 설비는 음수

        if is_lower:
            if val <= trip_th or z_score >= 4.0:
                return CircuitState.TRIP, f"압력 하한 트립 ({val} ≤ {trip_th} {unit})"
            if val <= warn_th or z_score >= 2.5 or (slope_warn < 0 and slope_per_sec <= slope_warn):
                return CircuitState.WARNING, f"압력 급락 조기 이상 ({val} {unit}, Z={z_score:.1f})"
        else:
            if val >= trip_th or z_score >= 4.0:
                return CircuitState.TRIP, f"온도 상한 트립 ({val} ≥ {trip_th} {unit})"
            if val >= warn_th or z_score >= 2.5 or (slope_warn > 0 and slope_per_sec >= slope_warn):
                return (
                    CircuitState.WARNING,
                    f"온도 급상승 조기 이상 ({val} {unit}, Z={z_score:.1f})",
                )
        return CircuitState.NORMAL, ""

    async def _trigger_early_warning_alert(
        self,
        *,
        eq_id: str,
        cb: dict[str, Any],
        sensor_id: str,
        value: float,
        severity: str,
        reason: str,
        z_score: float,
    ) -> None:
        """GraphRAG 하류 영향 + RAG 매뉴얼 가이드를 결합한 알람 생성 & Mongo 영속화."""
        alert_id = uuid.uuid4().hex[:10]
        eq_name = cb["equipment_name"]
        impact_path: list[str] = [eq_id]
        guide_summary: str | None = None

        if self._graph_repo:
            try:
                impact_res = await self._graph_repo.impact(eq_id)
                for item in impact_res.get("items", []):
                    impact_path.append(f"{item['impacted']} ({item['impacted_name']})")
            except Exception as exc:
                logger.warning("알람 하류 영향도 분석 실패", extra={"error": str(exc)})

        if self._milvus and self._redis:
            try:
                query_text = f"{eq_name} {cb['metric_name']} 알람 및 긴급 인터락 조치 대응 매뉴얼"
                vectors = await embed_texts(
                    [query_text], redis_client=self._redis, settings=self._settings
                )
                hits = search_manual_chunks(self._milvus, vectors[0], top_k=2)
                if hits:
                    guide_summary = (
                        f"[{hits[0].get('heading', '')}] {hits[0].get('text', '')[:250]}..."
                    )
            except Exception as exc:
                logger.warning("알람 매뉴얼 가이드 검색 실패", extra={"error": str(exc)})

        alert = EarlyWarningAlert(
            alert_id=alert_id,
            timestamp=datetime.now(UTC),
            severity=severity,
            equipment_id=eq_id,
            equipment_name=eq_name,
            sensor_id=sensor_id,
            metric_name=cb["metric_name"],
            value=value,
            unit=cb["unit"],
            reason=reason,
            z_score=z_score,
            impact_path=impact_path,
            guide_summary=guide_summary,
        )
        self._recent_alerts.append(alert)
        await self._persist_alert(alert)

        logger.warning(
            f"⚡ 조기 경보 발동 [{severity}]",
            extra={
                "alert_id": alert_id,
                "equipment": eq_name,
                "value": f"{value}{cb['unit']}",
                "reason": reason,
                "impact_count": len(impact_path) - 1,
            },
        )
        self._broadcast({"event": "alert", "data": alert.model_dump(mode="json")})

    async def _persist_alert(self, alert: EarlyWarningAlert) -> None:
        if self._mongo is None:
            return
        try:
            await self._mongo[ALERTS_COLLECTION].insert_one(alert.model_dump(mode="json"))
        except Exception as exc:
            logger.warning("알람 영속화 실패", extra={"error": str(exc)[:150]})

    async def _load_alerts_from_mongo(self) -> None:
        if self._mongo is None:
            return
        try:
            cursor = self._mongo[ALERTS_COLLECTION].find().sort("timestamp", -1).limit(30)
            docs = [doc async for doc in cursor]
            for doc in reversed(docs):  # 시간순으로 deque 적재
                doc.pop("_id", None)
                self._recent_alerts.append(EarlyWarningAlert(**doc))
            if docs:
                logger.info("알람 이력 복원", extra={"count": len(docs)})
        except Exception as exc:
            logger.warning("알람 이력 복원 실패", extra={"error": str(exc)[:150]})
