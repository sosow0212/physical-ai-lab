"""업로드 파일 저장소 — 로컬 볼륨(/data/uploads)에 연/월 디렉터리로 보관."""

import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings


class FileStorage:
    """업로드 원본 파일 관리 (api·worker가 같은 볼륨을 공유)."""

    def __init__(self, settings: Settings) -> None:
        self._base = Path(settings.upload_dir)

    def save(self, filename: str, content: bytes) -> str:
        """파일 저장 후 컨테이너 내부 경로 반환. 충돌 방지를 위해 uuid 접두."""
        suffix = Path(filename).suffix.lower()
        now = datetime.now(UTC)
        dir_ = self._base / f"{now:%Y}"
        dir_.mkdir(parents=True, exist_ok=True)
        path = dir_ / f"{uuid.uuid4().hex[:8]}_{self._safe_name(filename)}{suffix}"
        path.write_bytes(content)
        return str(path)

    def delete(self, path: str) -> None:
        Path(path).unlink(missing_ok=True)

    @staticmethod
    def _safe_name(filename: str) -> str:
        """경로 traversal 방지 + 파일명 정리."""
        stem = Path(filename).stem
        return "".join(c if c.isalnum() or c in "-_가-힣 " else "_" for c in stem)[:60] or "file"
