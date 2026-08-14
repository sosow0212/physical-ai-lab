"""리트리버 — dense 검색 + 이웃 청크 확장 + 제목 매핑."""

import logging
from dataclasses import dataclass

from pymilvus import MilvusClient
from redis.asyncio import Redis

from app.core.config import Settings
from app.infrastructure.milvus import query_manual_chunks, search_manual_chunks
from app.repositories.mongo.document_repository import DocumentRepository
from app.services.embedding_service import embed_texts

logger = logging.getLogger(__name__)

MAX_CONTEXT_CHARS = 4000
NEIGHBOR_EXPAND_TOP = 3  # 상위 N개 히트에 대해서만 앞/뒤 청크 확장


@dataclass
class RetrievedChunk:
    doc_id: str
    seq: int
    page: int
    heading: str
    text: str
    score: float


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    titles: dict[str, str]  # doc_id → 문서 제목

    @property
    def sources(self) -> list[dict]:
        """UI용 출처 목록 (상위 5개)."""
        return [
            {
                "type": "manual",
                "doc_id": c.doc_id,
                "title": self.titles.get(c.doc_id, "알 수 없음"),
                "page": c.page,
                "score": round(c.score, 3),
            }
            for c in self.chunks[:5]
        ]

    @property
    def context_block(self) -> str:
        """프롬프트 주입용 참고자료 블록."""
        parts = [
            f"[{i}] {self.titles.get(c.doc_id, '?')} p.{c.page} §{c.heading}\n{c.text}"
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
    ) -> None:
        self._milvus = milvus
        self._redis = redis
        self._documents = document_repo
        self._settings = settings

    async def retrieve(self, question: str) -> RetrievalResult:
        """질의 → 임베딩 → top-k 검색 → 이웃 확장 → 컨텍스트 조립."""
        vector = (await embed_texts([question], redis_client=self._redis, settings=self._settings))[
            0
        ]
        hits = search_manual_chunks(self._milvus, vector, top_k=self._settings.retrieval_top_k)
        chunks = [RetrievedChunk(**hit) for hit in hits]
        chunks = self._expand_neighbors(chunks)

        titles = {}
        for doc_id in {c.doc_id for c in chunks}:
            doc = await self._documents.find_by_id(doc_id)
            if doc:
                titles[doc_id] = doc.title
        return RetrievalResult(chunks=chunks, titles=titles)

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
        return self._trim_to_budget(ordered)

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
