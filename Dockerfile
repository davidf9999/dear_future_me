# ──────────────────────────────  builder  ──────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
  PIP_NO_CACHE_DIR=1

WORKDIR /code

COPY requirements.txt .

RUN apt-get update && \
  apt-get install -y --no-install-recommends gcc && \
  pip install --upgrade pip && \
  pip install -r requirements.txt && \
  apt-get purge -y gcc && \
  apt-get autoremove -y && \
  rm -rf /var/lib/apt/lists/*

# ──────────────────────────────  runtime  ──────────────────────────────
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY . /code

RUN /bin/sh -c ' \
  if [ "${DEMO_MODE:-true}" = "false" ] ; then \
  alembic upgrade head ; \
  fi \
  '

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
