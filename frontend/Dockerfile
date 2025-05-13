FROM python:3.11-slim-bookworm
# RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a non-root user and group
# Create home directory for appuser, set ownership, and then create user
# Also pre-create .streamlit directory and set its ownership
RUN groupadd -r appgroup && \
    mkdir -p /home/appuser/.streamlit && \
    useradd --no-log-init -r -g appgroup -d /home/appuser -s /bin/bash appuser && \
    chown -R appuser:appgroup /home/appuser
    
# Copy requirements first to leverage Docker cache
# Make sure you have a requirements.txt in your frontend directory
# for Streamlit and any other frontend-specific dependencies.
COPY --chown=appuser:appgroup ./frontend/requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy the rest of the application code
COPY --chown=appuser:appgroup . /app

# Switch to non-root user
USER appuser

EXPOSE 8501

# Default command to run Streamlit.
# This can be overridden by the 'command' in docker-compose.yml.
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--logger.level=info"]
