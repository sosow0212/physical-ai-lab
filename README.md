# Physical AI Lab (PAL)

스마트공장 공정 매뉴얼·설계도면 기반 RAG 챗봇 — **Vite + FastAPI 학습 프로젝트**

> 📚 **문서**
> - **[docs/WORKPLAN.md](docs/WORKPLAN.md)** — 프로젝트 작업서 (아키텍처·API·데이터 설계·마일스톤)
> - **[docs/PROGRESS.md](docs/PROGRESS.md)** — 현재 진행 상황 (Phase 0/1 완료, Phase 2 진행 중)
> - [AGENTS.md](AGENTS.md) — AI 에이전트 작업 가이드

## 빠른 시작

```bash
# 0) 사전 준비: .env의 GLM_API_KEY 확인 (GLM Coding Plan 키)
cp .env.example .env   # 최초 clone 시 — 키 입력 후 저장

# 1) 전체 스택 기동 (첫 회는 이미지 pull로 수 분 소요)
make up
# → 웹:    http://localhost:5173
# → API:   http://localhost:8000/docs
# → 헬스:  curl http://localhost:8000/api/v1/health

# 2) 샘플 데이터 생성 (매뉴얼 PDF 6종 + 도면 PNG 3종 → sample-data/)
make gen-data
```

종료는 `make down` (볼륨 유지) / 완전 초기화는 `make reset` (⚠️ 데이터 전부 삭제).

## 명령어 요약

| 명령 | 설명 |
|---|---|
| `make up` / `make down` | 스택 기동 / 종료 |
| `make up-debug` | 기동 + 웹 콘솔 (mongo-express:8911, attu:8912, redpanda-console:8913) |
| `make gen-data` | 샘플 매뉴얼 PDF·도면 PNG 생성 |
| `make logs s=api` | 특정 서비스 로그 팔로우 |
| `make ps` | 서비스 상태 확인 |
| `make build` | 백엔드 의존성 변경 시 이미지 재빌드 |
| `make test` / `make fmt` | 백엔드 테스트 / 포맷·린트 |
| `make reset` | 완전 초기화 (볼륨 삭제) |

## 접속 정보 (기동 후)

| 서비스 | URL |
|---|---|
| 프론트엔드 | http://localhost:5173 |
| API 문서(Swagger) | http://localhost:8000/docs |
| 헬스체크 | http://localhost:8000/api/v1/health |
| Neo4j 브라우저 | http://localhost:7474 (neo4j / `.env`의 `NEO4J_PASSWORD`) |
| Ollama | http://localhost:11434 |

## 기술 스택

FastAPI · MongoDB · Milvus · Neo4j · Redis · Redpanda(Kafka) · **GLM-4.6(z.ai Coding Plan, 채팅) + Ollama bge-m3(로컬 임베딩)** · Vite/React/TS · Docker Compose

> AI 설정(모델·온도·차원 등)은 전부 `.env`의 `LLM_*` / `EMBEDDING_*`로 관리합니다.

## 문제 해결

- **api 헬스가 `degraded`**: `make logs s=api`로 컴포넌트 상세 확인. mongo/redis/embedding 중 무엇이 down인지 `/api/v1/health`에 표시됩니다.
- **코드 수정이 반영 안 됨**: api는 폴링 reload(`WATCHFILES_FORCE_POLLING=true`)로 자동 반영됩니다. 의존성(pyproject) 변경은 `make build` 후 재기동해야 합니다.
- **GLM 오류(1113 잔액)**: `.env`의 `LLM_BASE_URL`이 `https://api.z.ai/api/coding/paas/v4`(Coding Plan 전용)인지 확인하세요. 일반 `paas/v4`는 별도 잔액이 필요합니다.
