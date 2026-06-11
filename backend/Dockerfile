FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY alembic.ini ./
COPY run_opencv_tests.py ./
COPY tests ./tests
COPY app ./app
COPY start.sh ./
RUN chmod +x start.sh && chmod -R o+rX /app

ENV HOME=/tmp
USER nobody

CMD ["./start.sh"]

