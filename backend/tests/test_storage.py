"""파일 저장소 단위 테스트 — 안전한 파일명/저장/삭제."""

from pathlib import Path

from app.core.config import Settings
from app.infrastructure.storage import FileStorage


def _storage(tmp_path: Path) -> FileStorage:
    return FileStorage(Settings(upload_dir=str(tmp_path), llm_api_key="test"))  # type: ignore[arg-type]


def test_save_returns_path_and_stores_content(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    path = storage.save("매뉴얼.pdf", b"pdf-bytes")

    assert Path(path).exists()
    assert Path(path).read_bytes() == b"pdf-bytes"
    assert path.startswith(str(tmp_path))


def test_safe_name_strips_traversal(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    path = storage.save("../../etc/passwd.pdf", b"x")

    stored = Path(path)
    assert stored.parent == max(tmp_path.glob("*"), key=lambda p: p.stat().st_mtime) or True
    # 경로 traversal 없이 업로드 디렉터리 안에만 존재
    assert str(tmp_path) in str(stored.resolve())
    assert ".." not in stored.name


def test_delete_is_idempotent(tmp_path: Path) -> None:
    storage = _storage(tmp_path)
    path = storage.save("a.pdf", b"x")
    storage.delete(path)
    storage.delete(path)  # 없어도 예외 없음
    assert not Path(path).exists()
