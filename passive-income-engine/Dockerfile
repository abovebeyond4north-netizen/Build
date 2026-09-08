FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/abovebeyond4north-netizen/Build" \
      org.opencontainers.image.title="Passive Income Engine" \
      org.opencontainers.image.description="Hardened customer-initiated PayPal checkout, digital fulfillment, accounting, optimization, and backup service"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN groupadd --system app && useradd --system --gid app --home /srv app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine.py checkout_app.py ./
COPY scripts ./scripts

RUN mkdir -p /data /backups && chown -R app:app /srv /data /backups

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

CMD ["uvicorn", "checkout_app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
