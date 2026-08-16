"""모의 공정 텔레메트리 Generator — Kafka(Redpanda) 스트림 발행.

시뮬레이션 대상 센서는 MonitorRegistry(그래프 SSOT)에서 로드한다.
base_mean/base_std 가 없는 센서(자동 등록 등)는 시뮬레이션에서 제외된다.
"""

import asyncio
import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaProducer

from app.core.config import Settings
from app.schemas.telemetry import GeneratorStatus, ScenarioType
from app.services.monitor_registry import DEFAULT_PROFILES, MonitorRegistry

logger = logging.getLogger(__name__)

TOPIC_TELEMETRY = "telemetry.line1"

# 센서 기본 프로필 (정상 기준치 및 표준편차)
#: 시뮬레이션 폴백 프로파일 — monitor_registry.DEFAULT_PROFILES 와 동일 (단일 정의 유지)
SENSOR_PROFILES: list[dict[str, Any]] = [vars(p).copy() for p in DEFAULT_PROFILES]


class TelemetryGenerator:
    def __init__(
        self,
        producer: AIOKafkaProducer,
        settings: Settings,
        registry: MonitorRegistry | None = None,
    ) -> None:
        self._producer = producer
        self._settings = settings
        self._registry = registry
        self._profiles: list[dict[str, Any]] = [dict(p) for p in SENSOR_PROFILES]
        self._is_running = False
        self._hz = 5  # 기본 초당 5건
        self._scenario = ScenarioType.NORMAL
        self._total_emitted = 0
        self._started_at: datetime | None = None
        self._task: asyncio.Task[None] | None = None
        self._drift_offset = 0.0

    @property
    def status(self) -> GeneratorStatus:
        return GeneratorStatus(
            is_running=self._is_running,
            hz=self._hz,
            scenario=self._scenario,
            total_emitted=self._total_emitted,
            started_at=self._started_at,
        )

    async def refresh_profiles(self) -> None:
        """레지스트리(그래프)에서 시뮬레이션 프로파일 로드 — base_mean/std 있는 센서만."""
        if self._registry is None:
            return
        try:
            profiles = (
                (await self._registry.load())
                if not self._registry.profiles
                else self._registry.profiles
            )
            simulated = [
                vars(p).copy()
                for p in profiles.values()
                if p.base_mean is not None and p.base_std is not None
            ]
            if simulated:
                self._profiles = simulated
                logger.info("시뮬레이터 프로파일 로드", extra={"count": len(simulated)})
        except Exception as exc:
            logger.warning(
                "시뮬레이터 프로파일 로드 실패 → 기본값 유지", extra={"error": str(exc)[:150]}
            )

    def start(self, hz: int = 5, scenario: ScenarioType = ScenarioType.NORMAL) -> GeneratorStatus:
        if self._is_running:
            self.set_scenario(scenario, hz)
            return self.status
        self._hz = hz
        self._scenario = scenario
        self._is_running = True
        self._started_at = datetime.now(UTC)
        self._drift_offset = 0.0
        self._task = asyncio.create_task(self._run_with_refresh())
        logger.info("텔레메트리 제너레이터 시작", extra={"hz": hz, "scenario": scenario})
        return self.status

    async def _run_with_refresh(self) -> None:
        await self.refresh_profiles()
        await self._run_loop()

    def stop(self) -> GeneratorStatus:
        if not self._is_running:
            return self.status
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._started_at = None
        logger.info("텔레메트리 제너레이터 정지", extra={"total_emitted": self._total_emitted})
        return self.status

    def set_scenario(self, scenario: ScenarioType, hz: int | None = None) -> GeneratorStatus:
        self._scenario = scenario
        if hz is not None:
            self._hz = hz
        if scenario == ScenarioType.NORMAL:
            self._drift_offset = 0.0
        logger.info("시나리오 변경", extra={"scenario": scenario, "hz": self._hz})
        return self.status

    def generate_single_sample(self, profile: dict[str, Any]) -> dict[str, Any]:
        """시나리오에 따라 단일 센서 텔레메트리 값 생성."""
        mean = profile["base_mean"]
        std = profile["base_std"]
        val = random.gauss(mean, std)
        is_lower = profile.get("is_lower_limit", False)

        if self._scenario == ScenarioType.NORMAL:
            # 100% 정상
            pass
        elif self._scenario == ScenarioType.ANOMALY_40:
            # 40% 확률로 주의/이상 발생
            if random.random() < 0.40:
                if is_lower:
                    val -= random.uniform(0.10, 0.16)
                else:
                    val += random.uniform(4.5, 7.5)
        elif self._scenario == ScenarioType.ANOMALY_70:
            # 70% 확률로 심각한 이상 발생
            if random.random() < 0.70:
                if is_lower:
                    val -= random.uniform(0.15, 0.22)
                else:
                    val += random.uniform(7.0, 11.0)
        elif self._scenario == ScenarioType.CRITICAL_SPIKE:
            # 즉각적인 인터락 트립 수준 스파이크
            if is_lower:
                val = profile["trip_threshold"] - random.uniform(0.04, 0.08)
            else:
                val = profile["trip_threshold"] + random.uniform(3.0, 6.0)
        elif self._scenario == ScenarioType.DRIFT:
            # 점진적 온도 상승 / 압력 강하
            self._drift_offset = min(self._drift_offset + 0.15, 14.0)
            if is_lower:
                val -= self._drift_offset * 0.02
            else:
                val += self._drift_offset

        val = round(val, 2)
        return {
            "msg_id": uuid.uuid4().hex,
            "timestamp": datetime.now(UTC).isoformat(),
            "line_id": "LINE-1",
            "equipment_id": profile["equipment_id"],
            "equipment_name": profile["equipment_name"],
            "sensor_id": profile["sensor_id"],
            "metric_name": profile["metric_name"],
            "value": val,
            "unit": profile["unit"],
            "warning_threshold": profile["warning_threshold"],
            "trip_threshold": profile["trip_threshold"],
            "is_lower_limit": is_lower,
            "scenario": self._scenario.value,
        }

    async def _run_loop(self) -> None:
        """주파수(hz)에 맞춰 Kafka로 주기적 발행."""
        try:
            while self._is_running:
                interval = 1.0 / max(self._hz, 1)
                # 센서 목록에서 라운드로빈 또는 동시 생성
                for profile in self._profiles:
                    if not self._is_running:
                        break
                    sample = self.generate_single_sample(profile)
                    key = profile["equipment_id"].encode("utf-8")
                    await self._producer.send_and_wait(
                        TOPIC_TELEMETRY,
                        value=sample,
                        key=key,
                    )
                    self._total_emitted += 1

                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("텔레메트리 발행 오류", extra={"error": str(exc)})
            self._is_running = False
