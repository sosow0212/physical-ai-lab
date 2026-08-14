"""구조화(JSON) 로깅 설정 — 모든 로그는 한 줄 JSON으로 출력된다.

로그 포맷을 JSON으로 통일하면 도커/ELK 등에서 파싱이 쉬워진다.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.core.config import Settings

#: LogRecord 기본 속성 — payload 에 병합하지 않는다 (컨텍스트 속성만 병합)
_RESERVED = frozenset(
    {
        "args",
        "msg",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "name",
        "message",
        "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """레코드를 JSON 한 줄로 직렬화하는 포매터."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(settings: Settings) -> None:
    """루트 로거에 JSON 핸들러를 부착한다. 앱 기동 시 1회만 호출."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # 시끄러운 서드파티 로거 등급 조정
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
