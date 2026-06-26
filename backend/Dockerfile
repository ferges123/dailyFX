FROM python:3.13-slim@sha256:c33f0bc4364a6881bed1ec0cc2665e6c53c87a43e774aaeab88e6f17af105e4f

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/pip pip install .

COPY alembic.ini ./
COPY healthcheck.py ./
COPY start.sh ./
RUN chmod +x start.sh && chmod -R o+rX /app

ENV HOME=/tmp
USER nobody

CMD ["./start.sh"]

