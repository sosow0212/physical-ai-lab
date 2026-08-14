"""PDF 구조 파서 — 폰트 크기 '분포 기반' 헤딩 감지.

절대 임계값(예: 12pt↑=헤딩)은 문서 생성기마다 본문 크기가 달라 실패한다.
(실제 사례: PowerPoint export 본문 12pt → 본문 전부가 헤딩으로 오분류)

전략:
  1. 1차 스캔: 문서 전체의 (텍스트, 폰트크기) 라인 수집
  2. 크기별 글자 수 가중치로 '본문 크기' = 최빈값 산출
  3. 본문보다 1.5pt 이상 큰 라인만 헤딩 후보 (길이 2~80자 + 문자/숫자 포함)
  4. 최대 크기 첫 등장 라인 = 표지 제목
  5. 폴백: 모든 라인이 헤딩으로만 분류된 경우 단일 섹션으로 병합 (빈 청크 방지)
"""

import asyncio
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

MAX_HEADING_LEN = 80
MIN_HEADING_LEN = 2
HEADING_MARGIN_PT = 1.5  # 본문 크기보다 이 값 이상 커야 헤딩
HAS_TEXT_RE = re.compile(r"[0-9A-Za-z가-힣]")  # 기호만으로 구성된 라인은 헤딩 제외


@dataclass
class ParsedSection:
    """헤딩 경로 + 본문 텍스트 (페이지 번호 포함)."""

    heading: str
    page: int
    text: str = ""
    heading_path: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    title: str
    sections: list[ParsedSection]
    page_count: int


def _collect_lines(doc: pymupdf.Document) -> list[tuple[int, str, float]]:
    """전체 페이지에서 (페이지번호, 라인텍스트, 최대폰트크기) 목록을 수집한다."""
    lines: list[tuple[int, str, float]] = []
    for page_no, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                if text:
                    lines.append((page_no, text, round(max(s["size"] for s in spans), 1)))
    return lines


def _body_size(lines: list[tuple[int, str, float]]) -> float:
    """글자 수 가중 최빈 폰트 크기 = 본문 크기."""
    counter: Counter[float] = Counter()
    for _, text, size in lines:
        counter[size] += len(text)
    return counter.most_common(1)[0][0] if counter else 10.5


def _is_heading(text: str, size: float, heading_min: float) -> bool:
    """헤딩 판정: 크기 + 길이 + 내용(기호만 라인 제외)."""
    if size < heading_min:
        return False
    if not MIN_HEADING_LEN <= len(text) <= MAX_HEADING_LEN:
        return False
    return bool(HAS_TEXT_RE.search(text))


def parse_pdf_sync(path: str) -> ParsedDocument:
    """PDF → 제목 + 섹션 목록. 문서별 적응형 임계값으로 헤딩을 감지한다."""
    doc = pymupdf.open(path)
    try:
        lines = _collect_lines(doc)
        body = _body_size(lines)
        heading_min = body + HEADING_MARGIN_PT
        title_size = max((size for _, _, size in lines), default=0.0)

        title = ""
        sections: list[ParsedSection] = []
        current: ParsedSection | None = None

        for page_no, text, size in lines:
            # 표지 제목: 최대 크기 라인의 첫 등장 (본문보다 확실히 클 때만)
            if not title and title_size >= heading_min + 2 and size >= title_size - 0.1:
                title = text
                continue
            if _is_heading(text, size, heading_min):
                current = ParsedSection(heading=text, page=page_no)
                sections.append(current)
                continue
            if current is None:  # 첫 헤딩 전 본문(표지 메타 등)
                current = ParsedSection(heading="문서 정보", page=page_no)
                sections.append(current)
            current.text += text + "\n"

        # 폴백: 모든 라인이 헤딩으로 분류돼 본문이 하나도 없으면 단일 섹션으로 병합
        if sections and all(not s.text.strip() for s in sections):
            merged_text = "\n".join(s.heading for s in sections)
            first_page = sections[0].page
            sections = [
                ParsedSection(heading="전체 내용", page=first_page, text=merged_text + "\n")
            ]

        page_count = doc.page_count
    finally:
        doc.close()

    if not sections:
        sections = [ParsedSection(heading="전체 내용", page=1)]
    for section in sections:
        section.heading_path = [title, section.heading] if title else [section.heading]
    return ParsedDocument(title=title or Path(path).stem, sections=sections, page_count=page_count)


async def parse_pdf(path: str) -> ParsedDocument:
    """파싱은 CPU/IO 블로킹 → 스레드 오프로드."""
    return await asyncio.to_thread(parse_pdf_sync, path)
