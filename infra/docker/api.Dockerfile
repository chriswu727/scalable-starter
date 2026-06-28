# syntax=docker/dockerfile:1.7
# =============================================================================
# FastAPI backend image. Multi-stage: a `dev` target with hot reload (used by
# docker-compose) and a small, non-root `runtime` target for production.
# Build context is the REPO ROOT:  docker build -f infra/docker/api.Dockerfile .
# =============================================================================
ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ---- builder: install pinned runtime dependencies into an isolated venv ----
FROM base AS builder
RUN python -m venv /opt/venv
COPY apps/api/pyproject.toml apps/api/README.md apps/api/requirements.txt /app/
COPY apps/api/app /app/app
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install --no-deps .

# ---- dev: editable install + dev tools + hot reload ----
FROM base AS dev
RUN python -m venv /opt/venv
COPY apps/api/pyproject.toml apps/api/README.md apps/api/requirements-dev.txt /app/
COPY apps/api/app /app/app
RUN pip install --upgrade pip \
    && pip install -r requirements-dev.txt \
    && pip install --no-deps -e .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ---- runtime: minimal, non-root, production ----
FROM base AS runtime
# Pin a numeric UID and reference USER by number: a non-numeric image user can't
# be verified against a pod's runAsNonRoot, so Kubernetes rejects the container.
RUN groupadd --system --gid 1000 app && useradd --system --uid 1000 --gid app --home /app app
COPY --from=builder /opt/venv /opt/venv
COPY apps/api /app
RUN chown -R app:app /app
USER 1000
EXPOSE 8000
# One process per pod: horizontal scale = more pods (the cluster scales out), and
# a single in-process Prometheus registry keeps /metrics counters correct.
# --proxy-headers trusts X-Forwarded-* from upstreams in FORWARDED_ALLOW_IPS
# (set it to the ingress/pod CIDR in production) so client IPs are accurate.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
