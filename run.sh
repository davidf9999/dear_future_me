#!/bin/bash

# Script to run the application in different environments (dev/prod/status)

if [ -z "$1" ] || { [ "$1" != "prod" ] && [ "$1" != "dev" ] && [ "$1" != "status" ]; }; then
  echo "Usage: $0 <prod|dev|status>"
  echo "Example: $0 prod     (to run production environment)"
  echo "         $0 dev      (to run development environment)"
  echo "         $0 status   (to check status of running services)"
  exit 1
fi

ACTION=$1
ENV_ARG=$2 # For status, this argument will be ignored if present, but captured

PID_DIR="./.pids" # Directory to store PID files

# Function to check process status
check_process_status() {
  local service_name="$1"
  local pid_file="$2"
  local process_pattern="$3" # Pattern to search for in ps output (e.g., "app.main:app", "streamlit run")
  local env_for_status_check="$4" # Added to specify which env we are checking for status output

  echo "--- Status for $service_name ($env_for_status_check) ---"
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file")
    if ps -p "$pid" -o comm= &>/dev/null; then
      echo "PID file ($pid_file) exists. Process with PID $pid is RUNNING."
      echo "Details (PID, PPID, STAT, ELAPSED, CMD):"
      ps -p "$pid" -o pid,ppid,stat,etime,args --no-headers
    else
      echo "PID file ($pid_file) exists, but process with PID $pid is NOT RUNNING (stale PID file)."
      # Optionally, you could offer to remove the stale PID file here.
    fi
  else
    echo "PID file ($pid_file) NOT found."
  fi

  echo "Searching for '$process_pattern' processes via ps aux..."
  # shellcheck disable=SC2009
  if ps aux | grep -v grep | grep --color=auto -q "$process_pattern"; then
    ps aux | grep -v grep | grep --color=auto "$process_pattern"
  else
    echo "No active process matching pattern '$process_pattern' found via ps."
  fi
  echo "--------------------------------------"
}


if [ "$ACTION" == "status" ]; then
  echo "Checking status for ALL environments (dev and prod)..."
  echo ""

  # Check Dev
  FASTAPI_PID_FILE_DEV="$PID_DIR/dev_fastapi.pid"
  STREAMLIT_PID_FILE_DEV="$PID_DIR/dev_streamlit.pid"
  # Load dev env to get port numbers for specific ps search
  if [ -f ".env.dev" ]; then
    # shellcheck disable=SC1091
    source ".env.dev"
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_DEV" "app.main:app.*--port $DFM_API_PORT.*--reload" "dev"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_DEV" "streamlit run streamlit_app.py.*--server.port $STREAMLIT_SERVER_PORT" "dev"
  else
    echo "WARNING: .env.dev not found. Cannot perform specific ps search for dev ports."
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_DEV" "app.main:app --reload" "dev"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_DEV" "streamlit run streamlit_app.py" "dev"
  fi

  # Check Prod
  FASTAPI_PID_FILE_PROD="$PID_DIR/prod_fastapi.pid"
  STREAMLIT_PID_FILE_PROD="$PID_DIR/prod_streamlit.pid"
  # Load prod env to get port numbers for specific ps search
  if [ -f ".env.prod" ]; then
    # shellcheck disable=SC1091
    source ".env.prod"
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_PROD" "app.main:app.*--port $DFM_API_PORT" "prod"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_PROD" "streamlit run streamlit_app.py.*--server.port $STREAMLIT_SERVER_PORT" "prod"
  else
    echo "WARNING: .env.prod not found. Cannot perform specific ps search for prod ports."
    check_process_status "FastAPI Server" "$FASTAPI_PID_FILE_PROD" "app.main:app" "prod"
    check_process_status "Streamlit App" "$STREAMLIT_PID_FILE_PROD" "streamlit run streamlit_app.py" "prod"
  fi

  exit 0
fi

# If action is dev or prod, ENV_TYPE is $ACTION
ENV_TYPE=$ACTION

echo "Attempting to start $ENV_TYPE environment..."

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
FASTAPI_PID_FILE="$PID_DIR/${ENV_TYPE}_fastapi.pid"
STREAMLIT_PID_FILE="$PID_DIR/${ENV_TYPE}_streamlit.pid"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Environment file $ENV_FILE not found."
    echo "Please create it based on .env.example and configure appropriately."
    exit 1
fi

mkdir -p "$PID_DIR" # Create PID directory if it doesn't exist

echo "Loading environment variables from $ENV_FILE..."
set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

# --- Create data directories (if defined in .env files) ---
if [ -n "$DATABASE_URL" ] && [[ "$DATABASE_URL" == sqlite*:///./* ]]; then
    DB_PATH_RELATIVE=$(echo "$DATABASE_URL" | sed 's|sqlite.*:///./||')
    mkdir -p "$(dirname "$DB_PATH_RELATIVE")"
    echo "Ensured database directory exists for: $DB_PATH_RELATIVE"
fi

if [ -n "$CHROMA_DIR" ]; then
    mkdir -p "$CHROMA_DIR"
    echo "Ensured ChromaDB directory exists: $CHROMA_DIR"
fi

# --- Start FastAPI Server ---
FASTAPI_LOG_FILE="./logs/${ENV_TYPE}_fastapi.log"
mkdir -p ./logs
echo "Starting FastAPI server ($ENV_TYPE) on $DFM_API_HOST:$DFM_API_PORT..."
if [ "$ENV_TYPE" == "prod" ]; then
    nohup uvicorn app.main:app --host "$DFM_API_HOST" --port "$DFM_API_PORT" > "$FASTAPI_LOG_FILE" 2>&1 &
    echo $! > "$FASTAPI_PID_FILE"
    echo "FastAPI ($ENV_TYPE) server started. PID: $(cat "$FASTAPI_PID_FILE"). Logs: $FASTAPI_LOG_FILE"
else # dev
    # For development, run with --reload. Logs to console by default.
    uvicorn app.main:app --host "$DFM_API_HOST" --port "$DFM_API_PORT" --reload &
    echo $! > "$FASTAPI_PID_FILE"
    echo "FastAPI ($ENV_TYPE) server started with --reload. PID: $(cat "$FASTAPI_PID_FILE")."
fi


# --- Start Streamlit App ---
STREAMLIT_LOG_FILE="./logs/${ENV_TYPE}_streamlit.log"
echo "Starting Streamlit app ($ENV_TYPE) on port $STREAMLIT_SERVER_PORT..."
if [ "$ENV_TYPE" == "prod" ]; then
    nohup streamlit run streamlit_app.py --server.port "$STREAMLIT_SERVER_PORT" --server.address "$DFM_API_HOST" --server.headless true > "$STREAMLIT_LOG_FILE" 2>&1 &
    echo $! > "$STREAMLIT_PID_FILE"
    echo "Streamlit ($ENV_TYPE) app started. PID: $(cat "$STREAMLIT_PID_FILE"). Logs: $STREAMLIT_LOG_FILE"
else # dev
    streamlit run streamlit_app.py --server.port "$STREAMLIT_SERVER_PORT" --server.address "$DFM_API_HOST" &
    echo $! > "$STREAMLIT_PID_FILE"
    echo "Streamlit ($ENV_TYPE) app started. PID: $(cat "$STREAMLIT_PID_FILE")."
fi

echo ""
echo "$ENV_TYPE Environment services started."
echo "To check status: ./run.sh status $ENV_TYPE"
echo "To stop the $ENV_TYPE FastAPI server: kill $(cat "$FASTAPI_PID_FILE") (or use ./stop.sh $ENV_TYPE)"
echo "To stop the $ENV_TYPE Streamlit app: kill $(cat "$STREAMLIT_PID_FILE") (or use ./stop.sh $ENV_TYPE)"

exit 0
