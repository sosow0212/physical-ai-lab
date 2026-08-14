# Physical AI Lab — 개발 오케스트레이션
# 사용법 요약: make help

COMPOSE ?= docker compose

.PHONY: help build up up-debug down reset ps logs bootstrap test fmt

help: ## 명령어 도움말
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

build: ## 이미지 빌드 (uv.lock 변경 시)
	$(COMPOSE) build

up: ## 전체 스택 기동 (기본)
	$(COMPOSE) up -d

up-debug: ## 기동 + 웹 콘솔(mongo-express/attu/redpanda-console)
	$(COMPOSE) --profile debug up -d

down: ## 종료 (볼륨 유지)
	$(COMPOSE) down

reset: ## 완전 초기화 (볼륨까지 삭제 — 주의)
	$(COMPOSE) down -v

ps: ## 서비스 상태 확인
	$(COMPOSE) ps

logs: ## 로그 팔로우 (예: make logs s=api)
	$(COMPOSE) logs -f $(s)

bootstrap: up ## 샘플 데이터 생성 + 시드 + 적재 (Phase 1/2 완료 후 전체 활성화)
	@echo ">> 샘플 데이터 시딩은 Phase 1(생성 스크립트) / Phase 2(업로드) 이후 활성화됩니다."
	@echo ">> 현재 상태: make ps 로 헬스 확인 → http://localhost:5173"

test: ## 백엔드 테스트
	cd backend && uv run pytest

fmt: ## 백엔드 포맷/린트
	cd backend && uv run ruff format . && uv run ruff check --fix
