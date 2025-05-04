#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# demo.sh: CLI demo for "Dear Future Me" text-based prototype
# Usage: TOKEN must be set to a valid Bearer token for an authenticated user
# =============================================================================

echo "\n=== STEP 1: Ingest theory document ==="
http POST localhost:8000/rag/ingest/ \
    namespace=theory \
    doc_id=theory1 \
    text="Small steps build hope. Each little action counts." \
    Authorization:"Bearer $TOKEN"

echo "\n=== STEP 2: Ingest personal plan document ==="
http POST localhost:8000/rag/ingest/ \
    namespace=personal_plan \
    doc_id=plan1 \
    text="Call Sara when in distress. Take a 5-minute walk if stressed." \
    Authorization:"Bearer $TOKEN"

echo "\n=== STEP 3: Ingest session transcript snippet ==="
http POST localhost:8000/rag/ingest/ \
    namespace=session_data \
    doc_id=session1 \
    text="Client: I feel hopeless. Therapist: " \
    Authorization:"Bearer $TOKEN"

# Pause to let embeddings persist
sleep 1

echo "\n=== STEP 4: Chat with RAG context ==="
echo "Client: I feel hopeless."
http POST localhost:8000/chat/text \
    message="I feel hopeless." \
    Authorization:"Bearer $TOKEN"

echo "\n=== STEP 5: Summarize the session ==="
http POST localhost:8000/rag/session/session1/summarize \
    Authorization:"Bearer $TOKEN"
