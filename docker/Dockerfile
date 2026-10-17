# Build: docker build -t pii-guard -f docker/Dockerfile .
#
# Unlike injection-guard, there is no license gate on the default model
# (en_core_web_lg is MIT, downloads anonymously — see README "Licensing"),
# which removes injection-guard's *reason* for deferring the download to
# container startup. So this bakes the model in at BUILD time instead —
# container startup has no network dependency on anything at all.

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# Baked in at build time, not pulled at startup — see header comment.
RUN python -m spacy download en_core_web_lg

# config.py's default (127.0.0.1) is correct for a non-containerized
# direct run; wrong inside a container, for the same reason documented
# in injection-guard's Dockerfile — Docker's port-publish targets the
# container's external interface, not its loopback. No AUTH_TOKEN branch
# exists here to reason about either way (see README "Why no hosted
# tier") — this daemon is never meant to be reachable from outside the
# machine it runs on, regardless of how this ENV is set.
ENV PII_GUARD_HOST=0.0.0.0

EXPOSE 8731

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8731/health', timeout=3)" || exit 1

CMD ["pii-guard-daemon"]
