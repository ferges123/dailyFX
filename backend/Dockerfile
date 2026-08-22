FROM python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY pyproject.toml requirements.lock ./
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv && \
    /opt/venv/bin/pip install --require-hashes --no-deps -r requirements.lock && \
    /opt/venv/bin/pip install --no-deps .

FROM python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/app ./app
COPY alembic.ini ./
COPY healthcheck.py ./
COPY start.sh ./
RUN chmod +x start.sh && chmod -R o+rX /app

ENV HOME=/tmp
USER nobody

CMD ["./start.sh"]
