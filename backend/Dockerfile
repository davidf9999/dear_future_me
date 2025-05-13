FROM python:3.11-slim-bookworm
# RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

# Copy requirements first to leverage Docker cache
COPY ./backend/requirements.txt /code/requirements.txt
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy application code and templates
COPY ./app /code/app
COPY ./templates /code/templates

# Create a dedicated writable directory for data as root
# This ensures the directory structure exists before changing ownership
RUN mkdir -p /data_vol/prod

# Now, change ownership of the application code directory (/code)
# and the dedicated data directory (/data_vol) to appuser
RUN chown -R appuser:appgroup /code
RUN chown -R appuser:appgroup /data_vol

# Switch to non-root user
USER appuser

EXPOSE 80
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]
