FROM python:3.14-slim

# curl is the fallback fetch path in app/ce_ingest.py when Python's own TLS egress fails.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

# Dependencies are their own layer so a code or CSV edit does not reinstall them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source is bind-mounted at run time (see docker-compose.yml); this COPY only makes the
# image usable on its own.
# Run unprivileged. uid 1000 is also the host owner of the bind-mounted code and data
# in development, so files the app writes there stay editable on the host. In an image
# without a bind mount, the copied code is owned by the same user so runtime writes
# under the working directory (caches, exports) still work.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app
COPY --chown=app:app . .

EXPOSE 8000

USER app

# data/beyondthecliff.db is a git-ignored build artifact, so a fresh checkout has no DB and
# app/db.py refuses to open. Build it on every start: the CSVs are small and this keeps the
# container's DB in step with whatever the CSVs say.
CMD ["sh", "-c", "python scripts/build_db.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
