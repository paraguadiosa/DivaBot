# syntax=docker/dockerfile:1
# DivaBot — the One, containerized. 💅
#
# Build:   docker build -t divabot .
# Run:     docker run --rm -e DISCORD_TOKEN=<token> divabot
#          (or better: use docker-compose.yml with profiles)

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first (cached layer).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Package + sources.
COPY pyproject.toml README.md LICENSE ./
COPY bot_discord.py bot_whatsapp.py llm_client.py ./
COPY scripts/ ./scripts/
RUN pip install --no-cache-dir --no-deps .

# Run as non-root — a diva does not need root, just attention.
RUN useradd --create-home --shell /usr/sbin/nologin diva
USER diva

# Default frontend: Discord. Override with `docker run --entrypoint diva-whatsapp` 
# or via `command:` in docker-compose.
ENTRYPOINT ["diva-discord"]
