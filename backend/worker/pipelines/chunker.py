"""구조 기반 청커 — 섹션(헤딩 경로) 단위 분할 + 최대 길이/오버랩 제어."""

import asyncio
from dataclasses import dataclass

from app.core.config import Settings
from worker.parser.pdf_parser import ParsedDocument


@dataclass
class Chunk:
    seq: int
    page: int
    heading: str
    text: str  # "[제목 > 헤딩] 본문" 형태 (검색 품질용 컨텍스트 프리픽스 포함)


def chunk_document_sync(parsed: ParsedDocument, settings: Settings) -> list[Chunk]:
    """섹션별로 본문을 잘라 청크 생성. 헤딩 경로를 프리픽스로 붙인다."""
    chunks: list[Chunk] = []
    max_chars = settings.chunk_max_chars
    overlap = settings.chunk_overlap_chars

    for section in parsed.sections:
        prefix = f"[{' > '.join(section.heading_path)}] "
        body_budget = max_chars - len(prefix)
        for piece in _split_body(section.text, body_budget, overlap):
            chunks.append(
                Chunk(
                    seq=len(chunks),
                    page=section.page,
                    heading=" > ".join(section.heading_path),
                    text=prefix + piece,
                )
            )
    return chunks


def _split_body(text: str, max_chars: int, overlap: int) -> list[str]:
    """문단 단위 결합 + 초과 시 오버랩 분할 (문자 하드슬릿 포함)."""
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    pieces: list[str] = []
    current = ""

    def flush() -> None:
        nonlocal current
        if current.strip():
            pieces.append(current.strip())
        current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 1 <= max_chars:
            current = f"{current}\n{paragraph}" if current else paragraph
            continue
        flush()
        tail = pieces[-1][-overlap:] if overlap and pieces else ""
        current = f"{tail} {paragraph}".strip() if tail else paragraph
        while len(current) > max_chars:  # 단일 문단이 예산 초과 → 하드 분할
            pieces.append(current[:max_chars])
            current = current[max_chars - overlap :]
    flush()
    return pieces


async def chunk_document(parsed: ParsedDocument, settings: Settings) -> list[Chunk]:
    return await asyncio.to_thread(chunk_document_sync, parsed, settings)
