FROM python:3.11-slim-bookworm
# RUN apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Create a non-root user and group
RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup appuser

# Copy requirements first to leverage Docker cache
COPY ./backend/requirements.txt /code/requirements.txt
RUN python -m pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy application code
# Ensure ownership is set to the new user
COPY ./app /code/app
COPY ./templates /code/templates

EXPOSE 80
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

# Create the base data directory structure as root first
RUN mkdir -p /code/data/prod

# Now, change ownership of everything under /code to appuser
RUN chown -R appuser:appgroup /code

# Switch to appuser BEFORE creating data dirs
USER appuser

# Create data directory as appuser for ephemeral SQLite and ChromaDB
# This RUN mkdir -p is now more of a verification or no-op if the dir exists,
# but it's good to keep as it ensures the appuser context.
# Alternatively, since appuser now owns /code/data, it can create /code/data/prod
# if it wasn't already created by the root mkdir.
# For clarity and to ensure appuser definitely can operate here:
RUN ls -ld /code/data && ls -ld /code/data/prod || mkdir -p /code/data/prod