"""조기 경보 시스템 단위 테스트 — 시나리오, 슬라이딩 윈도우, 서킷 브레이커 전이,
신규 설비 자동 등록(통계 전용), 레지스트리 리셋 검증."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.schemas.telemetry import CircuitState, ScenarioType
from app.services.anomaly_detector import AnomalyDetector
from app.services.monitor_registry import MonitorRegistry
from app.services.telemetry_service import SENSOR_PROFILES, TelemetryGenerator


def _make_generator() -> TelemetryGenerator:
    producer = MagicMock()
    settings = MagicMock(spec=Settings)
    return TelemetryGenerator(producer, settings)


def test_generator_scenarios_generate_within_expected_ranges():
    gen = _make_generator()
    tcu_profile = next(p for p in SENSOR_PROFILES if p["equipment_id"] == "TCU-100")

    # 1. NORMAL: 60도 부근
    gen.set_scenario(ScenarioType.NORMAL)
    normal_sample = gen.generate_single_sample(tcu_profile)
    assert 55.0 <= normal_sample["value"] <= 65.0
    assert normal_sample["scenario"] == "NORMAL"

    # 2. CRITICAL_SPIKE: 트립 기준(68) 초과
    gen.set_scenario(ScenarioType.CRITICAL_SPIKE)
    spike_sample = gen.generate_single_sample(tcu_profile)
    assert spike_sample["value"] >= 68.0

    # 3. DRIFT: 20회 호출 후 평균이 초기 base_mean(60)보다 확실히 상승
    gen.set_scenario(ScenarioType.DRIFT)
    drift_vals = [gen.generate_single_sample(tcu_profile)["value"] for _ in range(20)]
    avg = sum(drift_vals) / len(drift_vals)
    assert avg > tcu_profile["base_mean"] + 1.0, f"DRIFT 평균 {avg:.1f} 이 base_mean+1 미만"


@pytest.mark.anyio
async def test_anomaly_detector_sliding_window_and_circuit_breaker_transitions():
    settings = MagicMock(spec=Settings)
    detector = AnomalyDetector(settings)

    # 1. 정상 데이터 10건 주입 -> CircuitBreaker NORMAL 유지 (레지스트리 기본값 사용)
    await detector.reload_registry()
    for _ in range(10):
        sample = {
            "equipment_id": "TCU-100",
            "sensor_id": "TS-02",
            "value": 60.1,
        }
        await detector._process_sample(sample)

    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert cbs["TCU-100"].state == CircuitState.NORMAL
    assert cbs["TCU-100"].current_value == 60.1
    assert cbs["TCU-100"].z_score < 2.0

    # 2. 급격한 고온 데이터 주입 (66.0도 -> WARNING 임계 64도 초과)
    await detector._process_sample(
        {
            "equipment_id": "TCU-100",
            "sensor_id": "TS-02",
            "value": 66.0,
        }
    )
    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert cbs["TCU-100"].state == CircuitState.WARNING
    assert cbs["TCU-100"].current_value == 66.0

    # 3. 트립 한계 초과 (70.5도 -> TRIP 임계 68도 초과)
    await detector._process_sample(
        {
            "equipment_id": "TCU-100",
            "sensor_id": "TS-02",
            "value": 70.5,
        }
    )
    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert cbs["TCU-100"].state == CircuitState.TRIP

    # 4. 서킷 브레이커 리셋 -> NORMAL 복귀 / 모르는 ID는 404
    detector.reset_circuit_breaker("TCU-100")
    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert cbs["TCU-100"].state == CircuitState.NORMAL

    with pytest.raises(NotFoundError):
        detector.reset_circuit_breaker("UNKNOWN-999")


@pytest.mark.anyio
async def test_unknown_equipment_auto_registers_stat_only():
    """그래프에 없는 설비 텔레메트리 → 자동 등록(AUTO) 후 통계 전용 감시로 트립."""
    settings = MagicMock(spec=Settings)
    detector = AnomalyDetector(settings)
    await detector.reload_registry()

    # 미등록 설비 데이터 30건 → 자동 등록되어 NORMAL 유지 (창 충분히 채움)
    for _ in range(30):
        await detector._process_sample(
            {
                "equipment_id": "EQ-900",
                "sensor_id": "TS-99",
                "metric_name": "motor_temp",
                "value": 100.0,
                "unit": "°C",
            }
        )
    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert "EQ-900" in cbs
    assert cbs["EQ-900"].source == "auto"
    assert cbs["EQ-900"].threshold_warning is None  # 통계 전용
    assert cbs["EQ-900"].state == CircuitState.NORMAL

    # 급변 → Z-score 폭증 → 통계 전용 트립
    await detector._process_sample(
        {
            "equipment_id": "EQ-900",
            "sensor_id": "TS-99",
            "value": 140.0,
            "unit": "°C",
        }
    )
    await detector._process_sample(
        {
            "equipment_id": "EQ-900",
            "sensor_id": "TS-99",
            "value": 148.0,
            "unit": "°C",
        }
    )
    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert cbs["EQ-900"].state == CircuitState.TRIP


@pytest.mark.anyio
async def test_registry_loads_profiles_from_graph():
    """그래프 리포지토리에서 임계치를 포함한 프로파일 로드 (SSOT 검증)."""
    graph = MagicMock()
    graph.monitor_profiles = AsyncMock(
        return_value=[
            {
                "equipment_id": "EQ-600",
                "equipment_name": "2차 칠러",
                "sensor_id": "PS-02",
                "metric_name": "pressure",
                "unit": "MPa",
                "warning_threshold": "0.30",  # 그래프 props는 문자열로 저장될 수 있음
                "trip_threshold": "0.25",
                "is_lower_limit": "true",
                "base_mean": None,
                "base_std": None,
            },
        ]
    )
    registry = MonitorRegistry(graph)
    profiles = await registry.load()

    assert "EQ-600" in profiles
    p = profiles["EQ-600"]
    assert p.warning_threshold == 0.30 and p.trip_threshold == 0.25  # 문자열 → float 강제 변환
    assert p.is_lower_limit is True
    assert p.source == "graph"
    assert p.base_mean is None  # 시뮬레이션 제외 대상


@pytest.mark.anyio
async def test_chiller_lower_pressure_trip():
    settings = MagicMock(spec=Settings)
    detector = AnomalyDetector(settings)

    # CH-200 정상 주입 (0.42 MPa)
    await detector.reload_registry()
    for _ in range(5):
        await detector._process_sample(
            {
                "equipment_id": "CH-200",
                "sensor_id": "PS-01",
                "value": 0.42,
            }
        )
    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert cbs["CH-200"].state == CircuitState.NORMAL

    # 저압 트립 (0.22 MPa <= 0.25 MPa)
    await detector._process_sample(
        {
            "equipment_id": "CH-200",
            "sensor_id": "PS-01",
            "value": 0.22,
        }
    )
    cbs = {cb.equipment_id: cb for cb in detector.get_circuit_breakers()}
    assert cbs["CH-200"].state == CircuitState.TRIP
