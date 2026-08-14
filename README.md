# Physical AI Lab (PAL)

스마트공장 공정 매뉴얼·설계도면 기반 RAG 챗봇 — **Vite + FastAPI 학습 프로젝트**

> 🚧 구현 진행 중입니다. 전체 설계와 실행 계획은 아래 문서를 참고하세요.
>
> - **[docs/WORKPLAN.md](docs/WORKPLAN.md)** — 프로젝트 작업서 (아키텍처·API·데이터 설계·마일스톤)
> - **[docs/PROGRESS.md](docs/PROGRESS.md)** — 현재 진행 상황
> - [AGENTS.md](AGENTS.md) — AI 에이전트 작업 가이드

## 빠른 시작 (Phase 0 완료 후 활성화)

```bash
make bootstrap   # 샘플 데이터 생성 + 전체 스택 기동 + 시드 + 적재
# 웹:    http://localhost:5173
# API:   http://localhost:8000/docs
# 종료:  make down
```

사전 준비: [GLM Coding Plan](https://z.ai) API 키를 `.env`의 `GLM_API_KEY`에 설정 (LLM·임베딩은 z.ai API 사용, 로컬 GPU 불필요).

## 기술 스택
FastAPI · MongoDB · Milvus · Neo4j · Redis · Redpanda(Kafka) · GLM API(z.ai) · Vite/React/TS · Docker Compose
