"""청커 단위 테스트 — 분할/오버랩 규칙 검증."""

from app.core.config import Settings
from worker.parser.pdf_parser import ParsedDocument, ParsedSection
from worker.pipelines.chunker import chunk_document_sync


def _settings(**overrides) -> Settings:
    base = {
        "chunk_max_chars": "60",
        "chunk_overlap_chars": "10",
        "upload_dir": "/tmp/pal-test",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _doc(texts: list[str]) -> ParsedDocument:
    sections = [ParsedSection(heading=f"섹션 {i}", page=i + 1, text=t) for i, t in enumerate(texts)]
    for s in sections:
        s.heading_path = ["테스트 매뉴얼", s.heading]
    return ParsedDocument(title="테스트 매뉴얼", sections=sections, page_count=len(texts))


def test_chunk_has_heading_prefix() -> None:
    chunks = chunk_document_sync(_doc(["본문 내용입니다."]), _settings())
    assert len(chunks) == 1
    assert chunks[0].text.startswith("[테스트 매뉴얼 > 섹션 0]")
    assert "본문 내용입니다." in chunks[0].text


def test_long_text_splits_with_overlap() -> None:
    long_text = "\n".join(f"문단{i}" + "가" * 20 for i in range(10))
    chunks = chunk_document_sync(_doc([long_text]), _settings())
    assert len(chunks) > 1
    # 모든 청크가 예산(프리픽스 포함 60자) 이내
    assert all(len(c.text) <= 60 for c in chunks)
    # 순번 연속성
    assert [c.seq for c in chunks] == list(range(len(chunks)))


def test_short_sections_stay_separate() -> None:
    chunks = chunk_document_sync(_doc(["짧은 본문 하나", "짧은 본문 둘"]), _settings())
    assert len(chunks) == 2
    assert chunks[0].heading != chunks[1].heading
