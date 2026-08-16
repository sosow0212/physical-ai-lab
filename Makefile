# Physical AI Lab — 개발 오케스트레이션
# 사용법 요약: make help

COMPOSE ?= docker compose

.PHONY: help build up up-debug down reset ps logs bootstrap test fmt gen-data

help: ## 명령어 도움말
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}''

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

gen-data: ## 샘플 매뉴얼 PDF/도면 PNG 생성 (sample-data/)
	cd backend && uv run --group data python scripts/gen_sample_data.py

bootstrap: up ## 스택 기동 + 샘플 데이터 시드 (Phase 2 완료 후 업로드까지 자동화)
	$(MAKE) gen-data
	@echo ">> Phase 4 이후: graph reseed + 샘플 업로드가 여기에 추가됩니다."
	@echo ">> 현재 상태: make ps 로 헬스 확인 → http://localhost:5173"

test: ## 백엔드 테스트
	cd backend && uv run pytest

fmt: ## 백엔드 포맷/린트
	cd backend && uv run ruff format . && uv run ruff check --fix

telemetry-start: ## 텔레메트리 제너레이터 시작 (정상 모드)
	curl -s -X POST "http://localhost:8000/api/v1/telemetry/generator/start?hz=5&scenario=NORMAL" | jq .

telemetry-anomaly-40: ## 이상 40% 시나리오 주입
	curl -s -X POST http://localhost:8000/api/v1/telemetry/generator/scenario -H "Content-Type: application/json" -d '{"scenario":"ANOMALY_40","hz":10}' | jq .

telemetry-anomaly-70: ## 이상 70% 고위험 시나리오 주입
	curl -s -X POST http://localhost:8000/api/v1/telemetry/generator/scenario -H "Content-Type: application/json" -d '{"scenario":"ANOMALY_70","hz":10}' | jq .

telemetry-spike: ## 급격한 과열 스파이크 (트립 테스트) 주입
	curl -s -X POST http://localhost:8000/api/v1/telemetry/generator/scenario -H "Content-Type: application/json" -d '{"scenario":"CRITICAL_SPIKE"}' | jq .

telemetry-reset: ## 서킷 브레이커 전체 리셋
	curl -s -X POST http://localhost:8000/api/v1/telemetry/circuit-breaker/reset | jq .

telemetry-stop: ## 텔레메트리 제너레이터 정지
	curl -s -X POST http://localhost:8000/api/v1/telemetry/generator/stop | jq .

