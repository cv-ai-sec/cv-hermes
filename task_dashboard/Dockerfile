FROM python:3.12-slim

# Same fixed-UID pattern as hermes_agent/Dockerfile — this container also runs
# read_only: true + cap_drop: ALL in docker-compose.yml and shares the host-mounted
# ./data directory (owned by UID 10001) with hermes-agent.
RUN groupadd -g 10001 hermes && useradd -u 10001 -g hermes -M -s /usr/sbin/nologin hermes

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/task_dashboard

RUN mkdir -p /app/data && chown -R hermes:hermes /app

USER hermes

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "uvicorn", "task_dashboard.app:app", "--host", "0.0.0.0", "--port", "8000"]
