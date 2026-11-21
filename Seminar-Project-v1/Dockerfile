FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/appuser \
    PYTHAINLP_DATA=/home/appuser/pythainlp-data

WORKDIR /app

COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p "$PYTHAINLP_DATA" \
    && chown -R appuser:appuser /home/appuser

COPY app/ app/
COPY config/ config/
COPY db/ db/
COPY scripts/ scripts/
COPY web/ web/
COPY eval/sprint2/ eval/sprint2/
COPY output/sprint2/latest-test-both.json output/sprint2/latest-test-both.json
COPY output/presentation/offline-demo.html output/presentation/offline-demo.html
COPY demo_dashboard.py presentation_data.py ./

USER appuser

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/wms/health', timeout=2).read()"]

CMD ["python", "-m", "uvicorn", "demo_dashboard:app", "--host", "0.0.0.0", "--port", "8000"]
