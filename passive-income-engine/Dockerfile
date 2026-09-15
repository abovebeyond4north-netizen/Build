FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/abovebeyond4north-netizen/Build" \
      org.opencontainers.image.title="Passive Income Engine" \
      org.opencontainers.image.description="Hardened customer-initiated PayPal checkout, digital fulfillment, accounting, optimization, and backup service"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /srv

RUN groupadd --system app \
    && useradd --system --gid app --home /srv app \
    && python -m venv "$VIRTUAL_ENV" \
    && mkdir -p /data /backups \
    && chown -R app:app "$VIRTUAL_ENV" /data /backups

COPY --chown=app:app requirements.txt .

USER app
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app engine.py checkout_app.py hybrid.py ./
COPY --chown=app:app scripts ./scripts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "checkout_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
