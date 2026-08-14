"""PDF 구조 파서 테스트 — 적응형 헤딩 감지 (실제 PDF를 생성해 검증)."""

from pathlib import Path

import pymupdf

from worker.parser.pdf_parser import parse_pdf_sync


def make_pdf(path: Path, lines: list[tuple[str, float]]) -> Path:
    """테스트용 PDF 생성 — (텍스트, 폰트크기) 라인 목록을 한 페이지에 기록."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72.0
    for text, size in lines:
        page.insert_text((72, y), text, fontsize=size, fontname="korea")
        y += size + 8
    doc.save(str(path))
    doc.close()
    return path


def test_manual_style_headings(tmp_path: Path) -> None:
    """매뉴얼 스타일(본문 10.5pt/헤딩 13pt) → 헤딩 감지 + 본문 수집."""
    pdf = make_pdf(
        tmp_path / "m.pdf",
        [
            ("운전 매뉴얼", 20.0),  # 표지 제목
            ("1. 시스템 개요", 13.0),  # 헤딩
            ("본문 내용입니다.", 10.5),
            ("2. 절차", 13.0),
            ("절차 본문", 10.5),
        ],
    )
    parsed = parse_pdf_sync(str(pdf))

    assert parsed.title == "운전 매뉴얼"
    headings = [s.heading for s in parsed.sections]
    assert "1. 시스템 개요" in headings and "2. 절차" in headings
    body_by_heading = {s.heading: s.text for s in parsed.sections}
    assert "본문 내용입니다." in body_by_heading["1. 시스템 개요"]


def test_powerpoint_style_body_is_large(tmp_path: Path) -> None:
    """PowerPoint 스타일(본문 12pt, 조각난 단어 라인) → 본문이 헤딩으로 오분류되지 않음."""
    pdf = make_pdf(
        tmp_path / "ppt.pdf",
        [
            ("퇴사 프로세스", 54.0),  # 표지 제목
            ("퇴사", 12.0),  # 조각난 본문 (예전엔 헤딩으로 오분류)
            ("프로세스", 12.0),
            ("안내", 12.0),
            ("1. 의사 통보", 14.0),  # 소제목 (본문+1.5pt 이상)
            ("30일 전까지 통보합니다", 12.0),
        ],
    )
    parsed = parse_pdf_sync(str(pdf))

    assert parsed.title == "퇴사 프로세스"
    # 12pt 조각들은 헤딩이 아니라 본문이어야 한다
    headings = [s.heading for s in parsed.sections]
    assert "퇴사" not in headings and "프로세스" not in headings
    assert "1. 의사 통보" in headings
    joined = "\n".join(s.text for s in parsed.sections)
    assert "30일 전까지 통보합니다" in joined


def test_all_heading_fallback_merges(tmp_path: Path) -> None:
    """전 라인이 헤딩 크기인 문서 → 빈 섹션 대신 단일 섹션으로 병합 (청크 0 방지)."""
    pdf = make_pdf(
        tmp_path / "h.pdf",
        [
            ("큰제목", 24.0),
            ("단어", 24.0),
            ("조각", 24.0),
        ],
    )
    parsed = parse_pdf_sync(str(pdf))

    assert len(parsed.sections) == 1
    assert parsed.sections[0].heading == "전체 내용"
    assert "단어" in parsed.sections[0].text
