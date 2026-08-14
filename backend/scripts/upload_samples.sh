#!/usr/bin/env bash
# 샘플 매뉴얼 PDF를 공개 API로 업로드해 수집 파이프라인을 실제로 통과시킨다.
# 사용법: ./scripts/upload_samples.sh  (API 기본 http://localhost:8000)
set -euo pipefail

API="${API:-http://localhost:8000/api/v1}"
DIR="$(cd "$(dirname "$0")/../.." && pwd)/sample-data/manuals"

# API 기동 대기 (최대 60초)
for _ in $(seq 1 30); do
  curl -sf "$API/../health/live" >/dev/null 2>&1 && break
  sleep 2
done

for f in "$DIR"/*.pdf; do
  title=$(basename "$f" .pdf | tr '_' ' ')
  echo ">> 업로드: $title"
  curl -sf -X POST "$API/documents" -F "files=@$f" >/dev/null
done
echo ">> 업로드 완료 — 상태는 GET $API/documents 에서 확인"
