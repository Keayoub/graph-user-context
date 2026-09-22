FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /build
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN python -m pip install --upgrade pip && python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels
COPY src ./src
COPY graph_user_export.py obo_api.py ./
RUN mkdir -p /app/output && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "obo_api:app", "--host", "0.0.0.0", "--port", "8000"]