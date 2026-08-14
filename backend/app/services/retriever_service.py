"""리트리버 — dense 검색 + 이웃 청크 확장 + 도면 카드 병합 + 제목 매핑."""

import logging
from dataclasses import dataclass

from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.infrastructure.milvus import (
    ensure_drawing_cards,
    hybrid_search_manual_chunks,
    query_manual_chunks,
    search_drawing_cards,
    search_manual_chunks,
)
from app.repositories.mongo.document_repository import DocumentRepository
from app.repositories.mongo.drawing_repository import DrawingRepository
from app.services.embedding_service import embed_texts

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 4000
NEIGHBOR_EXPAND_TOP = 3  # 상위 N개 히트에 대해서만 앞/뒤 청크 확장
DRAWING_SCORE_THRESHOLD = 0.25  # 도면 출처 첨부 최소 유사도


@dataclass
class RetrievedChunk:
    doc_id: str  # manual: 문서 id / drawing: 도면 id
    seq: int
    page: int | None
    heading: str
    text: str
    score: float
    source_type: str = "manual"  # manual | drawing


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    titles: dict[str, str]  # doc_id → 표시 제목

    @property
    def sources(self) -> list[dict]:
        """UI용 출처 목록 (매뉴얼 상위 4 + 도면 상위 2)."""
        manuals = [c for c in self.chunks if c.source_type == "manual"][:4]
        drawings = [c for c in self.chunks if c.source_type == "drawing"][:2]
        return [
            {
                "type": c.source_type,
                "doc_id": c.doc_id,
                "title": self.titles.get(c.doc_id, "알 수 없음"),
                "page": c.page,
                "score": round(c.score, 3),
            }
            for c in manuals + drawings
        ]

    @property
    def context_block(self) -> str:
        """프롬프트 주입용 참고자료 블록."""
        parts = [
            f"[{i}] {self.titles.get(c.doc_id, '?')} "
            f"{'p.' + str(c.page) + ' ' if c.page else ''}§{c.heading}\n{c.text}"
            for i, c in enumerate(self.chunks, start=1)
        ]
        return "\n\n".join(parts)[:MAX_CONTEXT_CHARS]


class RetrieverService:
    def __init__(
        self,
        milvus: MilvusClient,
        redis: Redis,
        document_repo: DocumentRepository,
        settings: Settings,
        drawing_repo: DrawingRepository | None = None,
    ) -> None:
        self._milvus = milvus
        self._redis = redis
        self._documents = document_repo
        self._drawings = drawing_repo
        self._settings = settings
        ensure_drawing_cards(milvus, settings.embedding_dim)

    async def retrieve(self, question: str) -> RetrievalResult:
        """질의 → 임베딩 → 하이브리드(dense+BM25/RRF) 검색 + 도면 카드 → 컨텍스트 조립.

        하이브리드 검색 실패 시(구버전 컬렉션 등) dense 검색으로 폴백한다.
        """
        vector = (await embed_texts([question], redis_client=self._redis, settings=self._settings))[
            0
        ]
        try:
            hits = hybrid_search_manual_chunks(
                self._milvus, vector, question, top_k=self._settings.retrieval_top_k
            )
        except Exception as exc:
            logger.warning("하이브리드 검색 실패 → dense 폴백", extra={"error": str(exc)[:150]})
            hits = search_manual_chunks(self._milvus, vector, top_k=self._settings.retrieval_top_k)
        chunks = self._expand_neighbors([RetrievedChunk(**hit) for hit in hits])
        chunks = self._trim_to_budget(chunks) + self._search_drawings(vector)
        return RetrievalResult(chunks=chunks, titles=await self._resolve_titles(chunks))

    async def _resolve_titles(self, chunks: list[RetrievedChunk]) -> dict[str, str]:
        """doc_id → 표시 제목 매핑 (매뉴얼/도면 리포지토리 조회)."""
        titles: dict[str, str] = {}
        for chunk in chunks:
            if chunk.doc_id in titles:
                continue
            if chunk.source_type == "manual":
                doc = await self._documents.find_by_id(chunk.doc_id)
                if doc:
                    titles[chunk.doc_id] = doc.title
            elif self._drawings is not None:
                drawing = await self._drawings.find_by_id(chunk.doc_id)
                if drawing:
                    titles[chunk.doc_id] = f"{drawing.title} (Rev {drawing.revision})"
        return titles

    def _search_drawings(self, vector: list[float]) -> list[RetrievedChunk]:
        """도면 카드 검색 — 임계 이상만 출처로 첨부 (실패 시 조용히 스킵)."""
        if self._drawings is None:
            return []
        try:
            hits = search_drawing_cards(self._milvus, vector, top_k=3)
        except Exception as exc:
            logger.warning("도면 검색 실패(스킵)", extra={"error": str(exc)[:150]})
            return []
        return [
            RetrievedChunk(
                doc_id=h["drawing_id"],
                seq=0,
                page=None,
                heading=h["title"],
                text=f"설계도면: {h['title']} (Rev {h['revision']}) — {h['description']}",
                score=h["score"],
                source_type="drawing",
            )
            for h in hits
            if h["score"] >= DRAWING_SCORE_THRESHOLD
        ]

    def _expand_neighbors(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """상위 결과의 앞/뒤 청크(seq±1)를 끼워 넣어 문맥을 보강한다."""
        result: dict[tuple[str, int], RetrievedChunk] = {(c.doc_id, c.seq): c for c in chunks}
        for hit in chunks[:NEIGHBOR_EXPAND_TOP]:
            for seq in (hit.seq - 1, hit.seq + 1):
                if (hit.doc_id, seq) in result:
                    continue
                rows = query_manual_chunks(
                    self._milvus, f'doc_id == "{hit.doc_id}" and seq == {seq}'
                )
                for row in rows:
                    result[(hit.doc_id, seq)] = RetrievedChunk(
                        doc_id=row["doc_id"],
                        seq=row["seq"],
                        page=row["page"],
                        heading=row["heading"],
                        text=row["text"],
                        score=hit.score * 0.98,
                    )
        # 점수 내림차순 + 문서/순서 안정 정렬
        ordered = sorted(result.values(), key=lambda c: (-c.score, c.doc_id, c.seq))
        return ordered

    @staticmethod
    def _trim_to_budget(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        kept: list[RetrievedChunk] = []
        total = 0
        for chunk in chunks:
            if total + len(chunk.text) > MAX_CONTEXT_CHARS:
                break
            kept.append(chunk)
            total += len(chunk.text)
        return kept
