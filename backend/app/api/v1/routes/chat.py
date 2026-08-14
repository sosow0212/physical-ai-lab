"""채팅 API — 세션 관리 + 히스토리 + SSE 스트리밍 질의."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_chat_service
from app.schemas.chat import AskIn, MessageOut, SessionOut
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", status_code=201)
async def create_session(
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> SessionOut:
    return SessionOut.from_entity(await service.create_session())


@router.get("/sessions")
async def list_sessions(
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> list[SessionOut]:
    return [SessionOut.from_entity(s) for s in await service.list_sessions()]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str, service: Annotated[ChatService, Depends(get_chat_service)]
) -> None:
    await service.delete_session(session_id)


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: str, service: Annotated[ChatService, Depends(get_chat_service)]
) -> list[MessageOut]:
    return [MessageOut.from_entity(m) for m in await service.get_messages(session_id)]


@router.post("/sessions/{session_id}/messages/stream")
async def ask_stream(
    session_id: str,
    body: AskIn,
    request: Request,
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> StreamingResponse:
    """질의 → SSE 스트리밍 (sources / token / done / error)."""

    async def event_stream():
        try:
            async for event in service.ask_stream(session_id, body.question):
                data = json.dumps(event["data"], ensure_ascii=False)
                yield f"event: {event['event']}\ndata: {data}\n\n"
        except Exception as exc:  # 스트리밍 중 예기치 못한 오류
            data = json.dumps(
                {"code": "INTERNAL_ERROR", "message": str(exc)[:200]}, ensure_ascii=False
            )
            yield f"event: error\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
