"""문서 서비스 & API 단위 테스트 — 업로드 유효성 검증(Fast-fail) 및 청크 조회."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile

from app.core.errors import ValidationAppError
from app.services.document_service import DocumentService


def _dummy_service(milvus=None) -> DocumentService:
    settings = MagicMock()
    return DocumentService(
        document_repo=AsyncMock(),
        job_repo=AsyncMock(),
        producer=AsyncMock(),
        storage=MagicMock(),
        settings=settings,
        milvus=milvus,
    )


def test_validate_rejects_non_pdf_extension():
    service = _dummy_service()
    upload = MagicMock(spec=UploadFile)
    upload.filename = "manual.txt"
    with pytest.raises(ValidationAppError, match="PDF 파일"):
        service._validate(upload, b"some-content")


def test_validate_rejects_empty_content():
    service = _dummy_service()
    upload = MagicMock(spec=UploadFile)
    upload.filename = "manual.pdf"
    with pytest.raises(ValidationAppError, match="빈 파일"):
        service._validate(upload, b"")


def test_validate_rejects_invalid_magic_bytes():
    service = _dummy_service()
    upload = MagicMock(spec=UploadFile)
    upload.filename = "fake.pdf"
    with pytest.raises(ValidationAppError, match="헤더 불일치"):
        service._validate(upload, b"NOT_A_PDF_DATA_HERE")


def test_validate_rejects_corrupted_pdf_structure():
    service = _dummy_service()
    upload = MagicMock(spec=UploadFile)
    upload.filename = "corrupt.pdf"
    # Starts with %PDF but rest is corrupted garbage
    with pytest.raises(ValidationAppError, match="손상되었거나"):
        service._validate(upload, b"%PDF-1.4\ncorrupted garbage that cannot be parsed by pymupdf")


def test_validate_accepts_valid_pdf(tmp_path):
    import pymupdf

    # Create a minimal valid PDF in memory
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test Page Content")
    pdf_bytes = doc.tobytes()
    doc.close()

    service = _dummy_service()
    upload = MagicMock(spec=UploadFile)
    upload.filename = "valid_manual.pdf"

    # Should not raise
    service._validate(upload, pdf_bytes)


@pytest.mark.anyio
async def test_get_chunks_queries_milvus():
    milvus = MagicMock()
    # Mock Milvus query return
    milvus.query.return_value = [
        {"doc_id": "doc123", "seq": 1, "page": 2, "heading": "2. 가동", "text": "[매뉴얼 > 2. 가동] 본문 2"},
        {"doc_id": "doc123", "seq": 0, "page": 1, "heading": "1. 개요", "text": "[매뉴얼 > 1. 개요] 본문 1"},
    ]

    service = _dummy_service(milvus=milvus)
    service._documents.find_by_id_or_fail = AsyncMock(return_value=MagicMock(id="doc123", title="테스트"))

    doc, chunks = await service.get_chunks("doc123")
    assert doc.id == "doc123"
    assert len(chunks) == 2
    # Should be sorted by seq
    assert chunks[0]["seq"] == 0
    assert chunks[1]["seq"] == 1
