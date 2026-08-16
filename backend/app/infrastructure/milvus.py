"""Milvus 클라이언트 + 컬렉션 스키마 정의."""

import logging
from typing import Any

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

from app.core.config import Settings

logger = logging.getLogger(__name__)

COLLECTION_MANUAL_CHUNKS = "manual_chunks"
COLLECTION_DRAWING_CARDS = "drawing_cards"


def create_milvus_client(settings: Settings) -> MilvusClient:
    """Milvus 클라이언트 생성 (pymilvus 2.5 스타일)."""
    return MilvusClient(uri=settings.milvus_uri)


def ensure_manual_chunks(client: MilvusClient, dim: int) -> None:
    """manual_chunks 컬렉션 생성 (멱등). 하이브리드(BM25) 미지원 구버전은 재생성한다."""
    if client.has_collection(COLLECTION_MANUAL_CHUNKS):
        fields = {f["name"] for f in client.describe_collection(COLLECTION_MANUAL_CHUNKS)["fields"]}
        if "sparse" in fields:
            return
        # 구버전(하이브리드 전) → 재생성. 청크는 문서 재수집으로 복구한다.
        client.drop_collection(COLLECTION_MANUAL_CHUNKS)
        logger.warning("manual_chunks 스키마 마이그레이션 — 컬렉션 재생성 (문서 재수집 필요)")

    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("doc_id", DataType.VARCHAR, max_length=32)
    schema.add_field("seq", DataType.INT64)
    schema.add_field("page", DataType.INT64)
    schema.add_field("heading", DataType.VARCHAR, max_length=512)
    schema.add_field(
        "text",
        DataType.VARCHAR,
        max_length=8192,
        enable_analyzer=True,
        # 한국어는 공백 단위 단어 분리가 되어 standard 토크나이저로도 실용적
        # (Milvus 2.5.4 기본 제공 애널라이저: standard/english/chinese/japanese 등)
        analyzer_params={"type": "standard"},
    )
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim)
    schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
    # BM25 함수: text → sparse 벡터 자동 생성
    schema.add_function(
        Function(
            name="text_bm25",
            function_type=FunctionType.BM25,
            input_field_names=["text"],
            output_field_names=["sparse"],
        )
    )

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    index_params.add_index(
        field_name="sparse",
        index_type="SPARSE_INVERTED_INDEX",
        metric_type="BM25",
    )
    client.create_collection(COLLECTION_MANUAL_CHUNKS, schema=schema, index_params=index_params)
    logger.info(
        "Milvus 컬렉션 생성",
        extra={"collection": COLLECTION_MANUAL_CHUNKS, "dim": dim, "hybrid": True},
    )


def search_manual_chunks(
    client: MilvusClient,
    vector: list[float],
    *,
    top_k: int,
    filter_expr: str | None = None,
) -> list[dict[str, Any]]:
    """dense 검색 — COSINE distance → similarity(1-d) 로 변환해 반환."""
    results = client.search(
        collection_name=COLLECTION_MANUAL_CHUNKS,
        data=[vector],
        limit=top_k,
        anns_field="embedding",  # sparse(BM25) 인덱스와 공존 → 필드 명시 필수
        filter=filter_expr or "",
        output_fields=["doc_id", "seq", "page", "heading", "text"],
        search_params={"metric_type": "COSINE", "params": {"ef": 64}},
    )
    hits: list[dict[str, Any]] = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        hits.append(
            {
                "doc_id": entity["doc_id"],
                "seq": entity["seq"],
                "page": entity["page"],
                "heading": entity["heading"],
                "text": entity["text"],
                "score": 1.0 - hit["distance"],
            }
        )
    return hits


def hybrid_search_manual_chunks(
    client: MilvusClient,
    vector: list[float],
    question: str,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    """하이브리드 검색 — dense(HNSW) + sparse(BM25) 를 RRF로 융합.

    RRF 점수는 유사도가 아닌 순위 기반(≈0.03~0.06)이므로 score 필드는 참고용.
    """
    reqs = [
        AnnSearchRequest(
            data=[vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k,
        ),
        AnnSearchRequest(
            data=[question],
            anns_field="sparse",
            param={"metric_type": "BM25"},
            limit=top_k,
        ),
    ]
    results = client.hybrid_search(
        collection_name=COLLECTION_MANUAL_CHUNKS,
        reqs=reqs,
        ranker=RRFRanker(),
        limit=top_k,
        output_fields=["doc_id", "seq", "page", "heading", "text"],
    )
    hits: list[dict[str, Any]] = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        hits.append(
            {
                "doc_id": entity["doc_id"],
                "seq": entity["seq"],
                "page": entity["page"],
                "heading": entity["heading"],
                "text": entity["text"],
                "score": float(hit["distance"]),
            }
        )
    return hits


def query_manual_chunks(client: MilvusClient, filter_expr: str) -> list[dict[str, Any]]:
    """expr 로 행 조회 (이웃 청크 확장용)."""
    return list(
        client.query(
            collection_name=COLLECTION_MANUAL_CHUNKS,
            filter=filter_expr,
            output_fields=["doc_id", "seq", "page", "heading", "text"],
        )
    )


def delete_manual_chunks_by_doc(client: MilvusClient, doc_id: str) -> None:
    """문서 삭제/재수집 전 청크 정리 (expr 삭제)."""
    client.delete(collection_name=COLLECTION_MANUAL_CHUNKS, filter=f'doc_id == "{doc_id}"')


# ── 도면 카드 (제목·설명·설비 메타데이터 임베딩) ──


def ensure_drawing_cards(client: MilvusClient, dim: int) -> None:
    """drawing_cards 컬렉션이 없으면 생성한다 (멱등)."""
    if client.has_collection(COLLECTION_DRAWING_CARDS):
        return
    schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
    schema.add_field("id", DataType.INT64, is_primary=True)
    schema.add_field("drawing_id", DataType.VARCHAR, max_length=32)
    schema.add_field("title", DataType.VARCHAR, max_length=256)
    schema.add_field("description", DataType.VARCHAR, max_length=2048)
    schema.add_field("equipment", DataType.VARCHAR, max_length=64)
    schema.add_field("revision", DataType.INT64)
    schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=dim)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="HNSW",
        metric_type="COSINE",
        params={"M": 16, "efConstruction": 200},
    )
    client.create_collection(COLLECTION_DRAWING_CARDS, schema=schema, index_params=index_params)
    logger.info("Milvus 컬렉션 생성", extra={"collection": COLLECTION_DRAWING_CARDS, "dim": dim})


def search_drawing_cards(
    client: MilvusClient, vector: list[float], *, top_k: int = 3
) -> list[dict[str, Any]]:
    """도면 카드 dense 검색 — 채팅 출처 첨부용."""
    results = client.search(
        collection_name=COLLECTION_DRAWING_CARDS,
        data=[vector],
        limit=top_k,
        output_fields=["drawing_id", "title", "description", "equipment", "revision"],
        search_params={"metric_type": "COSINE", "params": {"ef": 64}},
    )
    hits: list[dict[str, Any]] = []
    for hit in results[0]:
        entity = hit.get("entity", {})
        hits.append(
            {
                "drawing_id": entity["drawing_id"],
                "title": entity["title"],
                "description": entity["description"],
                "equipment": entity.get("equipment", ""),
                "revision": entity.get("revision", 1),
                "score": 1.0 - hit["distance"],
            }
        )
    return hits


def delete_drawing_cards(client: MilvusClient, drawing_id: str) -> None:
    client.delete(collection_name=COLLECTION_DRAWING_CARDS, filter=f'drawing_id == "{drawing_id}"')
