"""영향범위 감지 단위 테스트 — 키워드/코드 규칙 검증."""

from app.services.impact_service import detect_target


def test_triggers_on_impact_keyword() -> None:
    assert detect_target("1번 라인 온도가 올라가는데 영향범위를 알려줘") == "TS-02"


def test_direct_equipment_code_wins() -> None:
    assert detect_target("VI-200이 오판정하면 영향은?") == "VI-200"


def test_keyword_map_variants() -> None:
    assert detect_target("냉각수 압력이 낮을 때 파급 효과는?") == "PS-01"
    assert detect_target("공기압 내려가면 연쇄 정지 되나요?") == "AC-30"


def test_no_trigger_returns_none() -> None:
    assert detect_target("금형온도 상한은 몇 도야?") is None  # 영향 키워드 없음
    assert detect_target("안녕하세요") is None
