# Use Python 3.11 with a specific digest to prevent supply chain attacks
FROM python:3.11-slim@sha256:4e5e9b05dda9cf699084f20ec3b1e09927f12a4e0cdedef3b4805a5b38607e36

# Set working directory
WORKDIR /app

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and configuration files
COPY ./app ./app
COPY alembic.ini .
COPY templates ./templates
COPY setup.py .

# Run database migrations
RUN alembic -c alembic.ini upgrade head

# Set proper permissions
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check - using the application's ping endpoint
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ping || exit 1

# Container metadata
LABEL maintainer="Your Organization" \
      version="1.0" \
      description="Dear Future Me Application"

# Note: Environment variables should be provided at runtime:
# - SECRET_KEY (required)
# - DATABASE_URL (default: sqlite+aiosqlite:///./demo.db)
# - OPENAI_API_KEY (required for non-demo mode)
# - ACCESS_TOKEN_EXPIRE_MINUTES (default: 60)
# - DEMO_MODE (default: false)

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
