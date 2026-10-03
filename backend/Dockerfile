# MCP Guardian backend — FastAPI + uvicorn on python:3.12-slim, non-root.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GUARDIAN_DB_PATH=/data/guardian.db

WORKDIR /app

COPY requirements.txt ./
# Runtime deps, plus the ASGI server. uvicorn is NOT in requirements.txt on
# purpose: that file is vendored into the Lambda artifact, where Mangum adapts
# the Lambda event to ASGI and a server would be dead weight. Container mode is
# the one place that needs a real server, so it is installed here.
RUN pip install --no-cache-dir -r requirements.txt "uvicorn[standard]>=0.30"

COPY app ./app

# Non-root runtime user; /data is the writable home for the SQLite database.
RUN useradd --create-home --uid 10001 guardian \
    && mkdir -p /data \
    && chown -R guardian:guardian /data

USER guardian

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
