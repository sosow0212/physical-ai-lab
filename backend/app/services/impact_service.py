"""영향범위 분석 서비스 — 질문에서 설비 감지 → 그래프 traversal → 컨텍스트화."""

import logging
import re

from app.repositories.neo4j.graph_repository import GraphRepository

logger = logging.getLogger(__name__)

TRIGGER_KEYWORDS = ("영향", "파급", "범위", "연쇄", "전파")
# 종료 경계를 \b 대신 (?![0-9]) — 한글이 \w 로 취급되어 'VI-200이' 같은 케이스 대응
CODE_RE = re.compile(r"(?<![A-Za-z0-9-])[A-Z]{2,4}-\d{2,3}(?!\d)")
LINE_RE = re.compile(r"(\d)\s*번\s*라인")

#: 도메인 키워드 → 대표 감시 센서/설비 (구체적인 키워드가 앞에 오도록 순서 유지)
KEYWORD_MAP: list[tuple[str, str]] = [
    ("금형온도", "TS-02"),
    ("금형 온도", "TS-02"),
    ("금형", "TS-02"),
    ("실린더", "TS-01"),
    ("노즐", "TS-01"),
    ("냉각수", "PS-01"),
    ("칠러", "CH-200"),
    ("검사실", "TS-03"),
    ("실내온도", "TS-03"),
    ("비전", "VI-200"),
    ("컨베이어", "CV-01"),
    ("압축공기", "AC-30"),
    ("공기압", "AC-30"),
    ("팔레타이저", "PL-01"),
    ("사출", "IH-250"),
    ("온도", "TS-02"),  # 라인 맥락에서 일반 '온도'는 금형온도로 간주
]


def detect_target(question: str) -> str | None:
    """질문에서 영향분석 대상 ID 감지: 직접 코드 > 키워드 매핑."""
    if not any(k in question for k in TRIGGER_KEYWORDS):
        return None
    if match := CODE_RE.search(question):
        return match.group(0)
    for keyword, target in KEYWORD_MAP:
        if keyword in question:
            return target
    return None


class ImpactService:
    def __init__(self, repo: GraphRepository) -> None:
        self._repo = repo

    async def analyze(self, question: str) -> dict | None:
        """감지 성공 시 traversal 결과 반환, 아니면 None (챗봇은 스킵)."""
        target_id = detect_target(question)
        if target_id is None:
            return None
        result = await self._repo.impact(target_id)
        if not result["items"]:
            return None
        return result

    @staticmethod
    def to_context(impact: dict) -> str:
        """영향분석 결과 → 프롬프트 [영향분석] 블록."""
        lines = [f"루트: {impact['root']}"]
        for item in impact["items"]:
            chain = "→".join(item["rels"])
            lines.append(
                f"- {item['impacted']} ({item['impacted_name']}, {item['impacted_label']}) "
                f"| 깊이 {item['depth']} | 경로 {chain}"
            )
        return "\n".join(lines)
