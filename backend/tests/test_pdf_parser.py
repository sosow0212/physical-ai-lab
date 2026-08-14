"""PDF 구조 파서 테스트 — 적응형 헤딩 감지 (실제 PDF를 생성해 검증).

본문 크기 판정은 '글자 수 가중 최빈 크기'이므로, 테스트 문서도 실제 문서처럼
본문이 헤딩보다 많은 구성으로 만든다.
"""

from pathlib import Path

import pymupdf

from worker.parser.pdf_parser import parse_pdf_sync


def make_pdf(path: Path, lines: list[tuple[str, float]]) -> Path:
    """테스트용 PDF 생성 — (텍스트, 폰트크기) 라인 목록을 한 페이지에 기록."""
    doc = pymupdf.open()
    page = doc.new_page()
    y = 60.0
    for text, size in lines:
        page.insert_text((50, y), text, fontsize=size, fontname="korea")
        y += size + 10
    doc.save(str(path))
    doc.close()
    return path


def test_manual_style_headings(tmp_path: Path) -> None:
    """매뉴얼 스타일(본문 10.5pt 다수/헤딩 13pt 소수) → 헤딩 감지 + 본문 수집."""
    pdf = make_pdf(tmp_path / "m.pdf", [
        ("운전 매뉴얼", 20.0),                       # 표지 제목
        ("1. 시스템 개요", 13.0),                    # 헤딩
        ("본문 내용 첫 번째 줄입니다 여기에 상세 설명이 들어갑니다.", 10.5),
        ("본문 내용 두 번째 줄입니다 파라미터와 절차를 기술합니다.", 10.5),
        ("2. 절차", 13.0),
        ("절차 본문 내용이 이어집니다 확인용 텍스트입니다.", 10.5),
    ])
    parsed = parse_pdf_sync(str(pdf))

    assert parsed.title == "운전 매뉴얼"
    headings = [s.heading for s in parsed.sections]
    assert "1. 시스템 개요" in headings and "2. 절차" in headings
    body_by_heading = {s.heading: s.text for s in parsed.sections}
    assert "상세 설명" in body_by_heading["1. 시스템 개요"]
    assert "절차 본문" in body_by_heading["2. 절차"]


def test_powerpoint_style_body_is_large(tmp_path: Path) -> None:
    """PowerPoint 스타일(본문 12pt, 조각난 단어 라인) → 본문이 헤딩으로 오분류되지 않음."""
    pdf = make_pdf(tmp_path / "ppt.pdf", [
        ("퇴사 프로세스", 54.0),   # 표지 제목
        ("퇴사", 12.0),            # 조각난 본문 (구버전 파서에서 헤딩으로 오분류되던 케이스)
        ("프로세스", 12.0),
        ("안내", 12.0),
        ("1. 의사 통보", 14.0),    # 소제목 (본문+1.5pt 이상)
        ("30일 전까지 통보합니다", 12.0),
    ])
    parsed = parse_pdf_sync(str(pdf))

    assert parsed.title == "퇴사 프로세스"
    headings = [s.heading for s in parsed.sections]
    assert "퇴사" not in headings and "프로세스" not in headings
    assert "1. 의사 통보" in headings
    joined = "\n".join(s.text for s in parsed.sections)
    assert "30일 전까지 통보합니다" in joined
    assert "안내" in joined


def test_uniform_size_document(tmp_path: Path) -> None:
    """전 라인이 같은 크기 → 빈 섹션 없이 단일 섹션에 전체 텍스트 보존 (청크 0 방지)."""
    pdf = make_pdf(tmp_path / "u.pdf", [
        ("첫 줄", 24.0),
        ("두 번째 줄", 24.0),
        ("세 번째 줄", 24.0),
    ])
    parsed = parse_pdf_sync(str(pdf))

    # 모든 라인이 본문으로 분류되어 하나 이상의 섹션에 텍스트가 존재해야 한다
    total_text = sum(len(s.text) for s in parsed.sections)
    assert total_text >= len("첫 줄") + len("두 번째 줄") + len("세 번째 줄")
