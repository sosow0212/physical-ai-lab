# AGENTS.md — AI 에이전트 작업 가이드

이 프로젝트에서 작업하는 AI 에이전트(Claude, Codex, 기타)는 아래 규칙을 따른다.

## 1. 시작하기 (모든 세션에서 필수)
1. `docs/WORKPLAN.md`를 **전체** 읽는다. → 프로젝트의 단일 진실 공급원(SSOT).
2. `docs/PROGRESS.md`를 읽고 **현재 Phase와 미완료 항목**을 확인한다.
3. `git log --oneline -10` 으로 최근 작업 맥락을 확인한다.

## 2. 작업 규칙
- 미완료 Phase의 체크리스트 항목부터 순서대로 진행한다. 건너뛰기 금지.
- **완료한 항목은 즉시 `docs/PROGRESS.md`를 `[x]`로 갱신**하고 작업 로그에 한 줄 추가한다.
- 설계·구조 변경이 필요하면 먼저 `docs/WORKPLAN.md`를 수정한 뒤 코드를 고친다 (문서 → 코드 순서).
- 컨벤션(§10) 준수: 레이어 의존성 방향, DTO/Entity 분리, 타입 힌트, Conventional Commits.
- 실행/종료 방법은 README.md와 WORKPLAN §9를 항상 동기화한다.

## 3. 아키텍치 요약 (상세는 WORKPLAN)
- `api`(FastAPI) + `worker`(Kafka consumer) + `frontend`(Vite+React)
- 데이터: MongoDB(메타) / Milvus(벡터) / Neo4j(영향범위 그래프) / Redis(캐시) / Redpanda(Kafka API)
- LLM/임베딩: **GLM Coding Plan(z.ai)** — glm-4.6 + embedding-3, OpenAI 호환 API. `.env`의 `GLM_API_KEY` 필수(커밋 금지). Provider 어댑터로 openai/ollama 교체 가능
- 백엔드 레이어: `routes → services → repositories`, `domain`은 순수 모델, DTO는 `schemas`

## 4. 자주 쓰는 명령
```bash
make up          # 기동 (프론트 http://localhost:5173, API http://localhost:8000/docs)
make logs s=api  # 로그
make down        # 종료
make reset       # 완전 초기화 (볼륨 삭제)
make bootstrap   # 샘플 데이터 생성 + 전체 기동 + 시드 + 업로드
```

> 시작 전 `.env`에 `GLM_API_KEY`(GLM Coding Plan 키)를 설정해야 한다.
