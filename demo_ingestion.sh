#!/usr/bin/env bash
# demo_ingestion.sh
#
# Re-ingests demo documents after wiping the existing demo collections.
# Works for both local runs and docker-compose (web + chroma).

set -euo pipefail

# ——————————————————————————————————————————
# Config
# ——————————————————————————————————————————
WEB_URL=${WEB_URL:-http://localhost:8000}
CHROMA_DIR=${CHROMA_DIR:-./chroma_data}          # must match Settings.CHROMA_DIR
DEMO_NS=("theory" "personal_plan" "session_data" "future_me")

echo "Target API : $WEB_URL"
echo "Chroma dir : $CHROMA_DIR"
echo

# ——————————————————————————————————————————
# 1. Purge previous demo collections
# ——————————————————————————————————————————
for ns in "${DEMO_NS[@]}"; do
  rm -rf "${CHROMA_DIR}/${ns}"* 2>/dev/null || true
done
echo "🧹  Cleared old demo collections."

# If you’re using the chroma Docker container with a *named* volume,
# wipe via docker exec instead:
# docker exec your_chroma_container rm -rf /data/*

# ——————————————————————————————————————————
# 2. Re-ingest demo docs
# ——————————————————————————————————————————
curl -sS -X POST "$WEB_URL/rag/ingest/" \
  -F namespace=theory        -F doc_id=theory_demo  \
  -F file=@demo_data/theory_excerpts.txt && echo

curl -sS -X POST "$WEB_URL/rag/ingest/" \
  -F namespace=personal_plan -F doc_id=plan_demo    \
  -F file=@demo_data/personal_plan.txt && echo

curl -sS -X POST "$WEB_URL/rag/ingest/" \
  -F namespace=session_data  -F doc_id=session_demo \
  -F file=@demo_data/session_notes.txt && echo

curl -sS -X POST "$WEB_URL/rag/ingest/" \
  -F namespace=future_me     -F doc_id=future_demo  \
  -F file=@demo_data/future_me_profile.txt && echo

echo "✅  Demo documents ingested cleanly."
