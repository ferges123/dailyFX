FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY healthcheck.py ./
COPY start.sh ./
RUN chmod +x start.sh && chmod -R o+rX /app

ENV HOME=/tmp
USER nobody

CMD ["./start.sh"]

