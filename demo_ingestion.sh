#!/bin/bash

# Script to ingest demo data into specified RAG namespaces.
# Usage: ./demo_ingestion.sh <dev|prod>

set -e # Exit immediately if a command exits with a non-zero status.

ENV_TYPE=$1
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$(realpath "$SCRIPT_DIR") # Assumes script is in project root

if [ -z "$ENV_TYPE" ]; then
  echo "Usage: $0 <dev|prod>"
  exit 1
fi

ENV_FILE="$PROJECT_ROOT/.env.$ENV_TYPE"

if [ ! -f "$ENV_FILE" ]; then
  echo "Error: Environment file $ENV_FILE not found."
  exit 1
fi

# Source environment variables to get DFM_API_PORT and CHROMA_DIR
# Use a subshell to avoid polluting the current shell's environment
(
  set -a # Automatically export all variables
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a

  if [ -z "$DFM_API_PORT" ]; then
    echo "Error: DFM_API_PORT not set in $ENV_FILE"
    exit 1
  fi
  if [ -z "$CHROMA_DIR" ]; then
    echo "Error: CHROMA_DIR not set in $ENV_FILE"
    exit 1
  fi

  API_BASE_URL="http://localhost:$DFM_API_PORT"
  INGEST_URL="$API_BASE_URL/rag/ingest/"

  # Namespaces from settings (ensure these match your app.core.settings.py)
  NAMESPACE_THEORY="theory"
  NAMESPACE_FUTURE_ME="future_me"
  # Add other namespaces as needed
  # NAMESPACE_PERSONAL_PLAN="personal_plan"
  # NAMESPACE_SESSION_DATA="session_data"
  # NAMESPACE_THERAPIST_NOTES="therapist_notes"
  # NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES="dfm_chat_history_summaries"


  echo "Targeting API: $API_BASE_URL"
  echo "Targeting Chroma Directory (for potential cleanup, though not directly used by curl): $CHROMA_DIR"
  echo "---"

  # Optional: Clean up existing collections in ChromaDB if DocumentProcessor handles it,
  # or if you have a separate cleanup mechanism.
  # For now, this script focuses on ingestion.
  # If DocumentProcessor creates collections if they don't exist, cleanup might not be needed here.
  # echo "Note: Manual cleanup of $CHROMA_DIR/$NAMESPACE_THEORY, etc., might be needed if re-ingesting identical doc_ids."

  # --- Ingest Theory Data ---
  echo "Ingesting into '$NAMESPACE_THEORY' namespace..."
  THEORY_FILES_DIR="$PROJECT_ROOT/demo_data/theory"
  if [ -d "$THEORY_FILES_DIR" ]; then
    for file_path in "$THEORY_FILES_DIR"/*.txt; do
      if [ -f "$file_path" ]; then
        doc_id=$(basename "$file_path" .txt)
        echo "  Ingesting $doc_id from $file_path..."
        curl -X POST "$INGEST_URL" \
          -H "Content-Type: multipart/form-data" \
          -F "namespace=$NAMESPACE_THEORY" \
          -F "doc_id=$doc_id" \
          -F "text=$(cat "$file_path")" \
          --silent --show-error --fail || echo "  Failed to ingest $doc_id"
        echo "" # Newline for readability
      fi
    done
  else
    echo "Warning: Directory $THEORY_FILES_DIR not found. Skipping theory ingestion."
  fi
  echo "---"

  # --- Ingest Future Me Data ---
  echo "Ingesting into '$NAMESPACE_FUTURE_ME' namespace..."
  FUTURE_ME_FILES_DIR="$PROJECT_ROOT/demo_data/future_me" # Assuming a similar structure
  if [ -d "$FUTURE_ME_FILES_DIR" ]; then
    for file_path in "$FUTURE_ME_FILES_DIR"/*.txt; do
      if [ -f "$file_path" ]; then
        doc_id=$(basename "$file_path" .txt) # Example: user1_future_narrative
        echo "  Ingesting $doc_id from $file_path..."
        curl -X POST "$INGEST_URL" \
          -H "Content-Type: multipart/form-data" \
          -F "namespace=$NAMESPACE_FUTURE_ME" \
          -F "doc_id=$doc_id" \
          -F "text=$(cat "$file_path")" \
          --silent --show-error --fail || echo "  Failed to ingest $doc_id"
        echo ""
      fi
    done
  else
    echo "Warning: Directory $FUTURE_ME_FILES_DIR not found. Skipping future_me ingestion."
  fi
  echo "---"
  
  # Add loops for other namespaces (personal_plan, session_data, etc.) as you create demo data for them.

  echo "Demo data ingestion process completed."
)
