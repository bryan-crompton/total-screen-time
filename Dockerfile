FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 7777

ENV SCREENTIME_SERVER_DB_PATH=/data/server.db
ENV SCREENTIME_SERVER_HOST=0.0.0.0
ENV SCREENTIME_SERVER_PORT=7777

CMD ["python", "-m", "uvicorn", "screentime.server.app:app", "--host", "0.0.0.0", "--port", "7777"]
