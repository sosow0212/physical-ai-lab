"""PDF 구조 파서 — 폰트 크기 기반 헤딩 감지."""

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

HEADING_MIN_SIZE = 12.0  # 13pt 섹션 헤딩 감지 (본문 10.5/9.5 와 분리)
TITLE_MIN_SIZE = 18.0  # 20pt 표지 제목
MAX_HEADING_LEN = 80


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


def parse_pdf_sync(path: str) -> ParsedDocument:
    """PDF → 제목 + 섹션 목록. 헤딩(폰트 크기) 기준으로 섹션을 시작한다."""
    doc = pymupdf.open(path)
    title = ""
    sections: list[ParsedSection] = []
    current: ParsedSection | None = None

    for page_no, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans).strip()
                max_size = max(s["size"] for s in spans)

                if max_size >= TITLE_MIN_SIZE and not title:
                    title = text
                    continue
                if max_size >= HEADING_MIN_SIZE and len(text) <= MAX_HEADING_LEN:
                    current = ParsedSection(heading=text, page=page_no)
                    sections.append(current)
                    continue

                if current is None:  # 첫 헤딩 전 본문(표지 메타 등) — '개요' 섹션으로 흡수
                    current = ParsedSection(heading="문서 정보", page=page_no)
                    sections.append(current)
                current.text += text + "\n"

    page_count = doc.page_count
    doc.close()

    # 헤딩 경로: 단순 1-depth (추후 다단 헤딩 확장 여지)
    for section in sections:
        section.heading_path = [title, section.heading] if title else [section.heading]
    return ParsedDocument(title=title or Path(path).stem, sections=sections, page_count=page_count)


async def parse_pdf(path: str) -> ParsedDocument:
    """파싱은 CPU/IO 블로킹 → 스레드 오프로드."""
    return await asyncio.to_thread(parse_pdf_sync, path)
