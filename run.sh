#!/bin/bash

# Script to run a specific application service (FastAPI or Streamlit)
# in the foreground for different environments (dev/prod), or to check status.

# --- Usage ---
# To run a service:
#   ./run.sh <prod|dev> <fastapi|streamlit>
# Example: ./run.sh dev fastapi  (runs FastAPI in dev mode in the current terminal)
#          ./run.sh prod streamlit (runs Streamlit in prod mode in the current terminal)
#
# To check status (uses ps aux, PID files are not primary for foreground processes):
#   ./run.sh status

# --- Argument Parsing ---
if [ "$1" == "status" ]; then
  ACTION="status"
  # No other arguments needed for status
elif [ -z "$1" ] || { [ "$1" != "prod" ] && [ "$1" != "dev" ]; } || \
     [ -z "$2" ] || { [ "$2" != "fastapi" ] && [ "$2" != "streamlit" ]; }; then
  echo "Usage:"
  echo "  $0 <prod|dev> <fastapi|streamlit>"
  echo "  $0 status"
  echo ""
  echo "Examples:"
  echo "  $0 dev fastapi     (to run FastAPI server in development mode)"
  echo "  $0 prod streamlit  (to run Streamlit app in production mode)"
  echo "  $0 status          (to check status of potentially running services)"
  exit 1
else
  ACTION="run_service"
  ENV_TYPE=$1
  SERVICE_NAME=$2
fi

PID_DIR="./.pids" # Kept for the status command, though less relevant for foreground

# --- Function to check process status ---
# Note: For foreground processes started by this script, PID files won't be created by run.sh.
# This function will primarily rely on 'ps aux' for checking.
check_process_status() {
  local service_display_name="$1" # More descriptive name for output
  local pid_file="$2"             # PID file path (may not exist for foreground)
  local process_pattern="$3"      # Pattern for ps aux
  local env_for_status_check="$4"

  echo "--- Status for $service_display_name ($env_for_status_check) ---"
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file")
    # Check if the process with this PID is actually running
    if ps -p "$pid" -o comm= >/dev/null; then
      echo "PID file ($pid_file) exists. Process with PID $pid is RUNNING."
      echo "Details (PID, PPID, STAT, ELAPSED, CMD):"
      ps -p "$pid" -o pid,ppid,stat,etime,args --no-headers
    else
      echo "PID file ($pid_file) exists, but process with PID $pid is NOT RUNNING (stale PID file)."
      echo "  This might indicate an unclean shutdown of a previously backgrounded process."
    fi
  else
    echo "PID file ($pid_file) NOT found (this is expected if services are run in foreground via this script)."
  fi

  echo "Searching for '$process_pattern' processes via 'ps aux'..."
  # shellcheck disable=SC2009
  if ps aux | grep -v grep | grep --color=auto -E -q "$process_pattern"; then # Using -E for extended regex
    ps aux | grep -v grep | grep --color=auto -E "$process_pattern"
  else
    echo "No active process matching pattern '$process_pattern' found via 'ps aux'."
  fi
  echo "--------------------------------------"
}

# --- Handle 'status' action ---
if [ "$ACTION" == "status" ]; then
  echo "Checking status for ALL environments (dev and prod) using 'ps aux'..."
  echo "Note: PID file checks are for previously backgrounded processes, not current foreground ones."
  echo ""

  # Check Dev
  FASTAPI_PID_FILE_DEV="$PID_DIR/dev_fastapi.pid"
  STREAMLIT_PID_FILE_DEV="$PID_DIR/dev_streamlit.pid"
  if [ -f ".env.dev" ]; then
    # shellcheck disable=SC1091
    source ".env.dev" # Load for DFM_API_PORT, STREAMLIT_SERVER_PORT
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_DEV" "app\.main:app.*--port $DFM_API_PORT.*--reload" "dev"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_DEV" "streamlit run frontend/streamlit_app\.py.*--server\.port $STREAMLIT_SERVER_PORT" "dev"
    set +o allexport # Unset variables after sourcing
  else
    echo "WARNING: .env.dev not found. Cannot perform specific ps search for dev ports."
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_DEV" "app\.main:app.*--reload" "dev"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_DEV" "streamlit run frontend/streamlit_app\.py" "dev"
  fi

  # Check Prod
  FASTAPI_PID_FILE_PROD="$PID_DIR/prod_fastapi.pid"
  STREAMLIT_PID_FILE_PROD="$PID_DIR/prod_streamlit.pid"
  if [ -f ".env.prod" ]; then
    # shellcheck disable=SC1091
    source ".env.prod" # Load for DFM_API_PORT, STREAMLIT_SERVER_PORT
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_PROD" "app\.main:app.*--port $DFM_API_PORT" "prod"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_PROD" "streamlit run frontend/streamlit_app\.py.*--server\.port $STREAMLIT_SERVER_PORT" "prod"
    set +o allexport # Unset variables after sourcing
  else
    echo "WARNING: .env.prod not found. Cannot perform specific ps search for prod ports."
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_PROD" "app\.main:app" "prod"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_PROD" "streamlit run frontend/streamlit_app\.py" "prod"
  fi
  exit 0
fi


# --- Handle 'run_service' action ---
echo "Attempting to start $SERVICE_NAME in $ENV_TYPE environment in the FOREGROUND..."
echo "Logs will appear in this terminal. Press Ctrl+C to stop."

# --- Git Branch Check (Enforcement) ---
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$ENV_TYPE" == "prod" ] && [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
  echo "--------------------------------------------------------------------"
  echo "ERROR: Production environment ('prod') can only be run from"
  echo "       the 'main' or 'master' branch."
  echo "       You are currently on branch '$CURRENT_BRANCH'."
  echo "--------------------------------------------------------------------"
  exit 1
elif [ "$ENV_TYPE" == "dev" ] && { [ "$CURRENT_BRANCH" == "main" ] || [ "$CURRENT_BRANCH" == "master" ]; }; then
  echo "--------------------------------------------------------------------"
  echo "ERROR: Development environment ('dev') should not be run from"
  echo "       the 'main' or 'master' branch to avoid confusion."
  echo "       You are currently on branch '$CURRENT_BRANCH'."
  echo "       Please switch to a development/feature branch."
  echo "--------------------------------------------------------------------"
  exit 1
else
  echo "INFO: Git branch '$CURRENT_BRANCH' is valid for '$ENV_TYPE' environment."
fi

# --- Environment File ---
ENV_FILE=".env.$ENV_TYPE"
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Environment file $ENV_FILE not found."
    echo "Please create it based on .env.example and configure appropriately."
    exit 1
fi

# Ensure a clean slate for SKIP_AUTH to prioritize .env file loading by Pydantic.
# This prevents an existing shell environment variable from overriding the .env setting.
unset SKIP_AUTH

echo "Loading environment variables from $ENV_FILE..."
set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
# Variables like DFM_API_HOST, DFM_API_PORT, STREAMLIT_SERVER_PORT are now set
set +o allexport

# --- Create data directories (if defined in .env files) ---
# These paths are relative to the project root where run.sh is executed.
# Ensure these match what your app expects when running locally (not in Docker).
if [ -n "$SQLITE_DB_PATH" ]; then # Using SQLITE_DB_PATH from .env.dev/.env.prod
    mkdir -p "$(dirname "$SQLITE_DB_PATH")"
    echo "Ensured database directory exists for: $SQLITE_DB_PATH"
fi

if [ -n "$CHROMA_DB_PATH" ]; then # Using CHROMA_DB_PATH from .env.dev/.env.prod
    mkdir -p "$CHROMA_DB_PATH"
    echo "Ensured ChromaDB directory exists: $CHROMA_DB_PATH"
fi

# --- Start Specified Service in Foreground ---
if [ "$SERVICE_NAME" == "fastapi" ]; then
    echo ""
    echo "Starting FastAPI server ($ENV_TYPE) on $DFM_API_HOST:$DFM_API_PORT in foreground..."
    echo "FastAPI logs will appear below. Press Ctrl+C to stop."
    echo "-----------------------------------------------------"
    if [ "$ENV_TYPE" == "prod" ]; then
        uvicorn app.main:app --host "$DFM_API_HOST" --port "$DFM_API_PORT"
    else # dev
        uvicorn app.main:app --host "$DFM_API_HOST" --port "$DFM_API_PORT" --reload
    fi
elif [ "$SERVICE_NAME" == "streamlit" ]; then
    echo ""
    echo "Starting Streamlit app ($ENV_TYPE) on port $STREAMLIT_SERVER_PORT in foreground..."
    echo "Streamlit app location: frontend/streamlit_app.py"
    echo "Streamlit logs will appear below. Press Ctrl+C to stop."
    echo "-----------------------------------------------------"
    # Adjust PYTHONPATH for local run if streamlit_app.py needs to import from root 'app'
    # This assumes run.sh is executed from the project root.
    export PYTHONPATH="${PYTHONPATH}:." 
    if [ "$ENV_TYPE" == "prod" ]; then
        # For prod, server.headless is good. Debug logging can be noisy but useful.
        streamlit run frontend/streamlit_app.py --server.port "$STREAMLIT_SERVER_PORT" --server.address "$DFM_API_HOST" --server.headless true --logger.level=debug
    else # dev
        streamlit run frontend/streamlit_app.py --server.port "$STREAMLIT_SERVER_PORT" --server.address "$DFM_API_HOST" --logger.level=debug
    fi
else
    # This case should not be reached due to argument parsing at the top, but good for safety.
    echo "Internal Error: Unknown service name '$SERVICE_NAME'. Should be 'fastapi' or 'streamlit'."
    exit 1
fi

# The script will block on the uvicorn or streamlit command until Ctrl+C is pressed.
echo ""
echo "$SERVICE_NAME ($ENV_TYPE) exited."
exit 0
