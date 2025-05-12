# #!/bin/bash

# # Script to stop the application services for a given environment (dev/prod)

# if [ -z "$1" ] || { [ "$1" != "prod" ] && [ "$1" != "dev" ]; }; then
#   echo "Usage: $0 <prod|dev>"
#   echo "Example: $0 prod  (to stop production environment services)"
#   echo "         $0 dev   (to stop development environment services)"
#   exit 1
# fi

# ENV_TYPE=$1
# PID_DIR="./.pids"
# FASTAPI_PID_FILE="$PID_DIR/${ENV_TYPE}_fastapi.pid"
# STREAMLIT_PID_FILE="$PID_DIR/${ENV_TYPE}_streamlit.pid"

# echo "Attempting to stop $ENV_TYPE environment services..."

# if [ -f "$FASTAPI_PID_FILE" ]; then
#     FASTAPI_PID=$(cat "$FASTAPI_PID_FILE")
#     echo "Stopping FastAPI server ($ENV_TYPE) with PID: $FASTAPI_PID..."
#     if ps -p "$FASTAPI_PID" > /dev/null; then
#        kill "$FASTAPI_PID"
#        # Add a small delay and check if process is actually killed
#        sleep 1
#        if ps -p "$FASTAPI_PID" > /dev/null; then
#            echo "Process $FASTAPI_PID did not stop with kill, trying kill -9..."
#            kill -9 "$FASTAPI_PID"
#        fi
#        echo "FastAPI server ($ENV_TYPE) stop signal sent."
#     else
#        echo "Process with PID $FASTAPI_PID not found. Removing stale PID file."
#     fi
#     rm "$FASTAPI_PID_FILE"
# else
#     echo "FastAPI server ($ENV_TYPE) PID file not found. Was it running?"
# fi

# if [ -f "$STREAMLIT_PID_FILE" ]; then
#     STREAMLIT_PID=$(cat "$STREAMLIT_PID_FILE")
#     echo "Stopping Streamlit app ($ENV_TYPE) with PID: $STREAMLIT_PID..."
#     if ps -p "$STREAMLIT_PID" > /dev/null; then
#        kill "$STREAMLIT_PID"
#        sleep 1
#        if ps -p "$STREAMLIT_PID" > /dev/null; then
#            echo "Process $STREAMLIT_PID did not stop with kill, trying kill -9..."
#            kill -9 "$STREAMLIT_PID"
#        fi
#        echo "Streamlit app ($ENV_TYPE) stop signal sent."
#     else
#        echo "Process with PID $STREAMLIT_PID not found. Removing stale PID file."
#     fi
#     rm "$STREAMLIT_PID_FILE"
# else
#     echo "Streamlit app ($ENV_TYPE) PID file not found. Was it running?"
# fi

# echo "$ENV_TYPE Environment services stop process complete."
