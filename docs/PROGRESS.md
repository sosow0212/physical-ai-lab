# 진행 상황 (Progress Tracker)

> AI 에이전트는 세션 시작 시 이 파일을 확인하여 **가장 아래 미완료 Phase부터** 작업을 이어간다.
> 작업 완료 시 해당 항목을 `[x]`로 변경하고, 한 줄 로그를 남긴다. 설계 변경이 발생하면 `docs/WORKPLAN.md`도 함께 수정한다.

## 현재 상태
- **진행 중인 Phase: 0**
- 마지막 업데이트: 2025-08-14 — LLM/임베딩을 GLM Coding Plan(z.ai)으로 변경 (구현 미착수)

---

## Phase 0 — 스캐폴딩 & 인프라
- [ ] 모노레포 디렉터리 생성 (backend/, frontend/, docker/, docs/, sample-data/)
- [ ] docker-compose.yml (mongo, redis, milvus+etcd+minio, neo4j, redpanda) — LLM은 외부 API(GLM z.ai)
- [ ] (선택) ollama 서비스를 local-llm 프로파일로 추가
- [ ] debug 프로파일 (mongo-express, attu, redpanda-console)
- [ ] Makefile (up/down/reset/logs/bootstrap)
- [ ] backend: pyproject.toml, uv 세팅, app 골격(빈 main.py)
- [ ] frontend: Vite React-TS 스캐폴드 + Tailwind
- [ ] .env.example (GLM_API_KEY 포함), .gitignore
- [ ] README.md (실행/종료 가이드 최초 작성)
- [ ] 검증: `make up` 후 모든 인프라 헬스체크 통과

## Phase 1 — 백엔드 골격 & 샘플 데이터
- [ ] core(config/logging/errors/lifespan)
- [ ] domain 모델 4종 + repositories 베이스(Mongo)
- [ ] api/v1 라우터 조립 + /health + 공통 에러 응답
- [ ] scripts/gen_sample_data.py — 매뉴얼 6종 PDF 생성
- [ ] scripts/gen_sample_data.py — 도면 3종 PNG 생성
- [ ] 검증: uvicorn 기동 + /health 200, sample-data/ 생성

## Phase 2 — 문서 수집 파이프라인
- [ ] infrastructure: kafka(producer), storage, milvus 클라이언트
- [ ] documents API (upload/list/detail/delete/reingest)
- [ ] ingestion_jobs API
- [ ] worker: consumer loop + 재시도/DLQ
- [ ] pdf_parser + chunker(구조 청킹)
- [ ] embedding_service + Redis 캐시
- [ ] manual_pipeline: Milvus 적재 + 상태 업데이트
- [ ] 검증: 샘플 PDF 업로드 → DONE → Milvus 검색 hits

## Phase 3 — RAG 챗봇
- [ ] llm_service (GLM z.ai 스트리밍 어댑터)
- [ ] retriever_service (top-k + 이웃확장)
- [ ] chat API (세션/메시지/SSE)
- [ ] chat_service (프롬프트 조립, 출처 수집, 히스토리)
- [ ] 프론트: 채팅 페이지(스트리밍, 출처 카드)
- [ ] 검증: "금형온도 임계값?" 질문에 출처 포함 스트리밍 답변

## Phase 4 — 지식그래프 & GraphRAG
- [ ] neo4j 인프라 클라이언트 + graph_repository
- [ ] seed_graph.py + POST /graph/reseed
- [ ] graph API (overview, impact)
- [ ] impact_service + chat 통합(설비 감지)
- [ ] 프론트: 그래프 페이지(영향 하이라이트)
- [ ] 검증: "1번 라인 온도 영향범위" → 그래프 근거 답변

## Phase 5 — 도면 관리
- [ ] drawings API (CRUD + 리비전 + 파일 스트림)
- [ ] drawing_pipeline (drawing_cards 적재)
- [ ] 챗봇 출처에 도면 첨부 + 뷰어
- [ ] 프론트: 도면 관리 페이지
- [ ] 검증: 도면 등록 → 챗봇이 관련 도면 원본 첨부

## Phase 6 — 다듬기
- [ ] 대시보드(통계/최근질문)
- [ ] 파이프라인 페이지(작업 목록/로그)
- [ ] 하이브리드 검색 (Milvus BM25 + RRF)
- [ ] pytest 보강 (services 단위 + 파서)
- [ ] README 최종 정리
- [ ] E2E 시나리오 3종 통과

## Phase 7 — (선택)
- [ ] k8s(k3s+Helm) 마이그레이션
- [ ] reranker, VL 도면 캡셔닝, 인증

---

## 작업 로그
| 날짜 | 작업 | 비고 |
|---|---|---|
| 2025-08-14 | docs/WORKPLAN.md 초안 작성 | 전체 설계 확정, 구현 미착수 |
| 2025-08-14 | LLM을 GLM Coding Plan(z.ai, glm-4.6 + embedding-3)으로 변경 | Ollama는 local-llm 선택 프로파일로 강등, EMBEDDING_DIM 2048 |
