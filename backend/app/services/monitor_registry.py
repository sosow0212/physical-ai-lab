"""모니터링 대상 레지스트리 — 설비/센서 감시 프로파일의 단일 진실 공급원(SSOT).

Neo4j 그래프의 Sensor 노드(props: metric_name/unit/warning_threshold/trip_threshold/
is_lower_limit/base_mean/base_std)가 마스터. 그래프를 사용할 수 없을 때는
DEFAULT_PROFILES 로 폴백한다.

동작:
  - load_profiles(): 그래프 우선 로드 → 실패/비면 기본값
  - auto_register(): 그래프에도 없는 설비의 텔레메트리가 오면 Equipment+Sensor
    노드를 자동 생성(auto_registered=true)하고 통계 전용(stat-only) 프로파일 반환.
    임계치는 엔지니어가 그래프 UI에서 나중에 채워 넣으면 즉시 반영된다.
"""

import logging
from dataclasses import dataclass, field

from app.repositories.neo4j.graph_repository import GraphRepository

logger = logging.getLogger(__name__)


@dataclass
class MonitorProfile:
    """설비 1대 감시 프로파일 (브레이커 임계치 + 시뮬레이터 파라미터)."""

    equipment_id: str
    equipment_name: str
    sensor_id: str
    metric_name: str
    unit: str
    warning_threshold: float | None
    trip_threshold: float | None
    is_lower_limit: bool = False
    base_mean: float | None = None  # 시뮬레이터용 (없으면 시뮬레이션 제외)
    base_std: float | None = None
    source: str = "graph"  # graph | default | auto
    props: dict = field(default_factory=dict)


#: 폴백 기본 프로파일 — 그래프 시드와 동일 값 (그래프 불가 시 사용)
DEFAULT_PROFILES: list[MonitorProfile] = [
    MonitorProfile(
        "TCU-100",
        "금형온도조절기",
        "TS-02",
        "mold_temperature",
        "°C",
        64.0,
        68.0,
        False,
        60.0,
        0.6,
        "default",
    ),
    MonitorProfile(
        "CH-200",
        "냉각수칠러",
        "PS-01",
        "chiller_pressure",
        "MPa",
        0.30,
        0.25,
        True,
        0.42,
        0.02,
        "default",
    ),
    MonitorProfile(
        "IH-250",
        "사출성형기",
        "TS-01",
        "cylinder_temp",
        "°C",
        238.0,
        245.0,
        False,
        220.0,
        1.2,
        "default",
    ),
    MonitorProfile(
        "VI-200",
        "비전검사기",
        "TS-03",
        "ambient_temp",
        "°C",
        29.0,
        32.0,
        False,
        24.0,
        0.5,
        "default",
    ),
    MonitorProfile(
        "AC-30",
        "스크류 컴프레서",
        "PS-AIR",
        "air_pressure",
        "MPa",
        0.60,
        0.50,
        True,
        0.76,
        0.03,
        "default",
    ),
]


def _to_float(value) -> float | None:
    """그래프 props는 문자열로 저장될 수 있어 강제 변환."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value) -> bool:
    return str(value).lower() in {"true", "1", "yes"}


class MonitorRegistry:
    """감시 프로파일 캐시 — 그래프가 마스터, 기본값/자동등록 폴백."""

    def __init__(self, graph_repo: GraphRepository | None) -> None:
        self._graph = graph_repo
        self._profiles: dict[str, MonitorProfile] = {}
        self._auto_registered: set[str] = set()

    @property
    def profiles(self) -> dict[str, MonitorProfile]:
        return self._profiles

    async def load(self) -> dict[str, MonitorProfile]:
        """그래프에서 프로파일 로드 (실패 시 기본값). 기존 브레이커 상태는 유지하기 위해
        프로파일만 교체하고 동작 중 상태는 호출자(detector)가 보존한다."""
        profiles: dict[str, MonitorProfile] = {}
        if self._graph is not None:
            try:
                rows = await self._graph.monitor_profiles()
                for row in rows:
                    eq_id = row["equipment_id"]
                    profiles[eq_id] = MonitorProfile(
                        equipment_id=eq_id,
                        equipment_name=row.get("equipment_name", eq_id),
                        sensor_id=row.get("sensor_id", ""),
                        metric_name=row.get("metric_name", ""),
                        unit=row.get("unit", ""),
                        warning_threshold=_to_float(row.get("warning_threshold")),
                        trip_threshold=_to_float(row.get("trip_threshold")),
                        is_lower_limit=_to_bool(row.get("is_lower_limit", False)),
                        base_mean=_to_float(row.get("base_mean")),
                        base_std=_to_float(row.get("base_std")),
                        source="graph",
                    )
            except Exception as exc:
                logger.warning(
                    "그래프 모니터 프로파일 로드 실패 → 기본값 폴백",
                    extra={"error": str(exc)[:150]},
                )

        if not profiles:
            profiles = {p.equipment_id: p for p in DEFAULT_PROFILES}
            logger.info("모니터 프로파일: 기본값 %d건 사용", len(profiles))
        else:
            logger.info("모니터 프로파일: 그래프에서 %d건 로드", len(profiles))

        self._profiles = profiles
        return profiles

    def get(self, equipment_id: str) -> MonitorProfile | None:
        return self._profiles.get(equipment_id)

    async def get_or_auto_register(self, sample: dict) -> MonitorProfile | None:
        """모르는 설비 텔레메트리 → 그래프에 Equipment+Sensor 자동 생성 후
        통계 전용(stat-only) 프로파일 반환."""
        eq_id = sample.get("equipment_id", "")
        sensor_id = sample.get("sensor_id", "")
        if not eq_id:
            return None
        if eq_id in self._profiles:
            return self._profiles[eq_id]
        if eq_id in self._auto_registered:  # 이미 시도함
            return self._profiles.get(eq_id)

        self._auto_registered.add(eq_id)
        eq_name = sample.get("equipment_name") or eq_id
        metric = sample.get("metric_name") or f"metric_{sensor_id or eq_id}".lower()
        unit = sample.get("unit", "")

        if self._graph is not None:
            try:
                await self._graph.auto_register_monitor(eq_id, eq_name, sensor_id, metric, unit)
            except Exception as exc:
                logger.warning(
                    "자동 등록 그래프 반영 실패(메모리에만 등록)", extra={"error": str(exc)[:150]}
                )

        profile = MonitorProfile(
            equipment_id=eq_id,
            equipment_name=eq_name,
            sensor_id=sensor_id,
            metric_name=metric,
            unit=unit,
            warning_threshold=None,  # 임계치 미정 → 통계(Z-score) 전용 감시
            trip_threshold=None,
            source="auto",
        )
        self._profiles[eq_id] = profile
        logger.info(
            "신규 설비 자동 등록 (통계 전용)",
            extra={"equipment_id": eq_id, "sensor_id": sensor_id, "unit": unit},
        )
        return profile
