#!/usr/bin/env bash
# demo_ingestion.sh
#
# Re-ingests demo documents after wiping the existing demo collections.
# Works for both local runs and docker-compose (web + chroma).

set -euo pipefail

if [ -z "$1" ] || { [ "$1" != "prod" ] && [ "$1" != "dev" ]; }; then
  echo "Usage: $0 <prod|dev>"
  echo "Example: $0 dev   (to ingest demo data for the development environment)"
  echo "         $0 prod  (to ingest demo data for the production environment)"
  exit 1
fi

ENV_TYPE=$1
ENV_FILE=".env.$ENV_TYPE"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Environment file $ENV_FILE not found for environment '$ENV_TYPE'."
    exit 1
fi

# Load environment-specific variables (WEB_URL, CHROMA_DB_PATH)
echo "Loading environment variables from $ENV_FILE..."
set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE" # This will set DFM_API_URL and CHROMA_DB_PATH
set +o allexport

# ——————————————————————————————————————————
# Config
# ——————————————————————————————————————————
DEMO_NS=("theory" "personal_plan" "session_data" "future_me")

echo "Target API ($ENV_TYPE) : $DFM_API_URL" # Use DFM_API_URL from sourced .env file
echo "Chroma dir ($ENV_TYPE) : $CHROMA_DB_PATH" # Use CHROMA_DB_PATH from sourced .env file
echo

# ——————————————————————————————————————————
# 1. Purge previous demo collections
# ——————————————————————————————————————————
for ns in "${DEMO_NS[@]}"; do
  rm -rf "${CHROMA_DB_PATH}/${ns:?}"* 2>/dev/null || true # Consistently use CHROMA_DB_PATH and ensure ns is set
done
echo "🧹  Cleared old demo collections."

# If you’re using the chroma Docker container with a *named* volume,
# wipe via docker exec instead:
# docker exec your_chroma_container rm -rf /data/*

# ——————————————————————————————————————————
# 2. Re-ingest demo docs
# ——————————————————————————————————————————
curl -sS -X POST "$DFM_API_URL/rag/ingest/" \
  -F namespace=theory        -F doc_id=theory_demo  \
  -F file=@demo_data/theory_excerpts.txt && echo

curl -sS -X POST "$DFM_API_URL/rag/ingest/" \
  -F namespace=personal_plan -F doc_id=plan_demo    \
  -F file=@demo_data/personal_plan.txt && echo

curl -sS -X POST "$DFM_API_URL/rag/ingest/" \
  -F namespace=session_data  -F doc_id=session_demo \
  -F file=@demo_data/session_notes.txt && echo

curl -sS -X POST "$DFM_API_URL/rag/ingest/" \
  -F namespace=future_me     -F doc_id=future_demo  \
  -F file=@demo_data/future_me_profile.txt && echo

echo "✅  Demo documents ingested cleanly."
