# 진행 상황 (Progress Tracker)

> AI 에이전트는 세션 시작 시 이 파일을 확인하여 **가장 아래 미완료 Phase부터** 작업을 이어간다.
> 작업 완료 시 해당 항목을 `[x]`로 변경하고, 한 줄 로그를 남긴다. 설계 변경이 발생하면 `docs/WORKPLAN.md`도 함께 수정한다.

## 현재 상태
- **진행 중인 Phase: 7 (선택)** — Phase 0~6 완료, 핵심 기능 전부 E2E 통과
- 마지막 업데이트: 2025-08-14 — Phase 5/6 완료 (도면 관리 + 대시보드/파이프라인/하이브리드 검색)

---

## Phase 0 — 스캐폴딩 & 인프라 ✅
- [x] 모노레포 디렉터리 생성 (backend/, frontend/, docs/, sample-data/)
- [x] docker-compose.yml (mongo, redis, milvus+etcd+minio, neo4j, redpanda, ollama) — LLM 채팅은 외부 API(GLM z.ai)
- [x] ollama는 로컬 임베딩(bge-m3) 담당 코어 서비스로 확정 (ADR 참조)
- [x] debug 프로파일 (mongo-express, attu, redpanda-console)
- [x] Makefile (up/down/reset/logs/build/gen-data/bootstrap)
- [x] backend: pyproject.toml + uv 세팅, 앱 팩토리 골격
- [x] frontend: Vite React-TS 스캐폴드 + Tailwind (사이드바 셸)
- [x] .env.example (GLM_API_KEY 포함), .gitignore (.env 커밋 제외 확인)
- [x] README.md (실행/종료 가이드)
- [x] 검증: `make up` 후 전 서비스 healthy + Vite 프록시 + 컨테이너 내 GLM 채팅/bge-m3 임베딩 실측 통과

## Phase 1 — 백엔드 골격 & 샘플 데이터 ✅
- [x] core(config/logging/errors/lifespan) + 요청 ID 미들웨어
- [x] domain 모델 4종 (document/drawing/chat/ingestion_job, StrEnum)
- [x] repositories 베이스(MongoRepository, PEP 695 제네릭) + 구현체 4종
- [x] api/v1 라우터 조립 + /health(컴포넌트별 상태) + /health/live + 공통 에러 봉투
- [x] scripts/gen_sample_data.py — 매뉴얼 6종 PDF 생성 (fpdf2+NanumGothic)
- [x] scripts/gen_sample_data.py — 도면 3종 PNG 생성 (matplotlib, 타이틀 블록 포함)
- [x] 검증: ruff/pytest 통과, 도커 /health 전 컴포넌트 ok, 텍스트 추출 품질(폰트 크기 20/13/10.5/9.5 분포) 확인

## Phase 2 — 문서 수집 파이프라인 ✅
- [x] infrastructure: kafka(producer/이벤트 봉투), milvus(컬렉션/검색/expr 삭제), storage(연도별 저장)
- [x] documents API (upload 202/list/detail/delete/reingest) + pipeline jobs API
- [x] worker: aiokafka consumer(수동 커밋) + 재시도 3회(5/15/45s) + DLQ
- [x] pdf_parser(폰트 크기 헤딩 감지) + chunker(헤딩 프리픽스/오버랩/하드분할)
- [x] embedding_service(bge-m3 배치 + Redis 캐시) + manual_pipeline(Milvus 적재/설비 태깅)
- [x] 검증: 샘플 6종 업로드→DONE, 38청크, '금형온도' 질의로 정확 청크 검색

## Phase 3 — RAG 챗봇 ✅
- [x] llm_service (GLM SSE 스트리밍 파싱, reasoning_content 제외)
- [x] retriever_service (top-k + 이웃 청크 확장 + 제목 매핑 + 컨텍스트 예산)
- [x] chat API (세션 CRUD/히스토리/SSE: sources·graph·token·done·error)
- [x] chat_service (시스템 프롬프트/히스토리 6턴/출처 저장/세션 제목 갱신)
- [x] 프론트: 챗 페이지(스트리밍 렌더/출처 칩), 매뉴얼 관리(업로드/폴링/재수집/삭제)
- [x] GLM thinking 토글 env 추가 (LLM_THINKING, RAG는 disabled 기본 — 토큰 소진 이슈 해결)
- [x] 검증: '금형온도 상한/인터락' → TCU 매뉴얼 p.2 근거 답변 스트리밍

## Phase 4 — 지식그래프 & GraphRAG ✅
- [x] neo4j driver + graph_repository (시드=문장 리스트 실행/overview/impact traversal/DESCRIBES)
- [x] seed: LINE-1 설비 9·센서 4·관계 26종 (FEEDS/AFFECTS/MONITORS/…)
- [x] graph API (overview/impact/reseed dev 전용)
- [x] impact_service (설비 코드/키워드 감지 — 한글 \b 이슈 해결) + chat 통합(graph 이벤트/프롬프트 블록/장애 격리)
- [x] 워커: 수집 완료 시 Document-[:DESCRIBES]->Equipment 자동 연결
- [x] 프론트: 그래프 페이지(force-graph, 클릭 시 영향 하이라이트+사이드 패널)
- [x] 검증: '1번 라인 온도 영향범위' → TS-02→IH-250→VI-200→PL-01 그래프 근거 + 매뉴얼 p.2 인용 답변

## Phase 5 — 도면 관리 ✅
- [x] drawings API (등록 multipart/목록/PATCH 자동 재수집/리비전 rev+1/삭제/원본 스트림)
- [x] drawing_cards 컬렉션 + DrawingPipeline(메타 텍스트 임베딩)
- [x] worker 파이프라인 Protocol 통합 라우팅 (manual/drawing)
- [x] 챗봇 출처에 도면 첨부(임계 0.25) + 라이트박스 뷰어
- [x] 프론트: 도면 관리 페이지(그리드/모달/리비전/뷰어)
- [x] 검증: '냉각수 배관 압력계 위치?' → 매뉴얼+도면 복합 출처, 답변에 관련 도면 섹션

## Phase 6 — 다듬기 ✅
- [x] stats API + 대시보드(지표 카드/최근 질문/작업 요약, 10s 폴링)
- [x] 파이프라인 페이지(상태 필터/자동 새로고침/에러 표시)
- [x] 하이브리드 검색 — Milvus BM25(sparse+Function, standard 애널라이저) + RRF, 구버전 컬렉션 자동 마이그레이션(drop+재생성+재수집), 실패 시 dense 폴백
- [x] pytest 13종 (헬스 3 + 영향감지 4 + 청커 3 + 저장소 3)
- [x] README 최종 정리 (전체 기능 안내)
- [x] E2E 3종 통과: ①수집 DONE 6종+도면 3종 ②매뉴얼+도면 출처 ③TS-02 그래프 영향범위 + 1706자 스트리밍 답변

## Phase 7 — (선택)
- [ ] k8s(k3s+Helm) 마이그레이션
- [ ] reranker, VL 도면 캡셔닝, 인증

---

## 작업 로그
| 날짜 | 작업 | 비고 |
|---|---|---|
| 2025-08-14 | docs/WORKPLAN.md 초안 작성 | 전체 설계 확정, 구현 미착수 |
| 2025-08-14 | LLM을 GLM Coding Plan(z.ai, glm-4.6 + embedding-3)으로 변경 | Ollama는 local-llm 선택 프로파일로 강등, EMBEDDING_DIM 2048 |
| 2025-08-14 | Phase 0 완료 — compose 스택 11종 전부 healthy, GLM 채팅 실측 통과 | api 컨테이너에서 코딩 플랜 엔드포인트(/api/coding/paas/v4) 검증 |
| 2025-08-14 | 임베딩을 로컬 Ollama bge-m3(1024d)로 확정 (하이브리드) | Coding Plan에 임베딩 API 부재 실측. ollama 코어 서비스화 + bge-m3 자동 pull |
| 2025-08-14 | Phase 1 완료 — 백엔드 골격(레이어/도메인/리포지토리/헬스) + 샘플 데이터 9종 생성 | ruff+pytest 통과, /health 전 컴포넌트 ok, PDF 텍스트 추출 검증 |
| 2025-08-14 | Phase 2/3/4 완료 — 수집 파이프라인→SSE 챗봇→GraphRAG E2E 통과 | 샘플 6종 자동 수집(38청크), TCU 근거 답변, TS-02 영향범위 그래프+매뉴얼 복합 답변 실측. GLM thinking 토글(env) 추가 |
| 2025-08-14 | Phase 5/6 완료 — 도면 관리·대시보드·파이프라인·하이브리드 검색(BM25+RRF) | Milvus 2.5.4에 korean 애널라이저 부재→standard 채택(ADR), 컬렉션 자동 마이그레이션+전체 재수집, E2E 3종 통과. 채팅 스트리밍은 Vite 프록시 경유 점진 도착 실측 완료 |
| 2026-08-15 | UX 개선 6건 — ①채팅 마크다운 렌더링 ②출처/매뉴얼 클릭→원본 뷰어(PDF 페이지 앵커) ③glm-5.3 승격 ④그래프 노드명·관계 한글 표시 + 노드/관계 CRUD(화이트리스트) ⑤매뉴얼 PDF 뷰어 ⑥사이드바 등 디자인 개선 · PDF 파서 적응형 임계값 교체(퇴사 PDF 12청크 수집 성공) | 사용자 피드백 반영 |
| 2026-08-15 | 조기 경보 시스템(EWS) 리팩터링 — 감시 대상 SSOT를 Neo4j 그래프로 통일(MonitorRegistry): 그래프 편집→reload 즉시 반영/삭제 동기화, 모르는 설비 텔레메트리 자동등록(그래프 노드 생성+통계전용 감시), slope 초당 정규화(hz 무관), reset 404, 알람 Mongo 영속화, RAG 가이드 anns_field 버그 수정, 챗봇 자동 질의(?ask=) 연동, 대시보드 EWS 위젯 | 사용자 검토 요청 — 설비 하드코딩 3곳 중복 문제 해결. 실측: 그래프 추가→감시 반영, EQ-900 자동등록, 트립 알람+GraphRAG 경로+가이드 정상 |
| 2026-08-15 | 업로드 에러 원인 명시 & Fast-Fail 예외 + 그래프 ID 직관화 & 줌/간격 조절 도구 + PDF 인라인 뷰어/별도 다운로드 + 청크 뷰어 모달 및 전략 문서화(docs/INGESTION_STRATEGY.md) | 사용자 요구사항 3건 완료 |

