# Build: docker build -t pii-guard -f docker/Dockerfile .
#
# Unlike injection-guard, there is no license gate on the default model
# (en_core_web_lg is MIT, downloads anonymously — see README "Licensing"),
# which removes injection-guard's *reason* for deferring the download to
# container startup. en_core_web_lg is a direct pip dependency (see
# pyproject.toml) — `uv sync` pulls it like any other package, baked
# into the image at build time, no separate download step. (It used to
# be a separate `spacy download` RUN line here; that masked a real
# packaging gap — `uv tool install` has no equivalent manual step, so
# the daemon crash-looped on first real install outside this
# Dockerfile. Fixed at the dependency level instead, see pyproject.toml.)

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN uv sync --frozen --no-dev
ENV PATH="/app/.venv/bin:$PATH"

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
