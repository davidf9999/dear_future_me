#!/usr/bin/env bash
# demo_ingestion.sh
#
# Ingest the four demo documents into the RAG store.
# Accepts an optional WEB_URL env-var so it works both locally
# (localhost:8000) and inside docker-compose (http://web:8000).

set -euo pipefail

WEB_URL=${WEB_URL:-http://localhost:8000}

echo "Ingesting demo data into $WEB_URL …"

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

echo "✅  Demo documents ingested."
