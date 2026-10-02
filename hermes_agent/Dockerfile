FROM python:3.12-slim

# Non-root, fixed-UID user — never run the agent as root or as an
# unpredictable UID, since docker-compose.yml also sets read_only: true
# and cap_drop: ALL and expects this exact UID to own /workspace and /var/log/hermes.
RUN groupadd -g 10001 hermes && useradd -u 10001 -g hermes -M -s /usr/sbin/nologin hermes

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/hermes_agent

RUN mkdir -p /workspace /var/log/hermes \
    && chown -R hermes:hermes /workspace /var/log/hermes /app

USER hermes

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "hermes_agent.main"]
