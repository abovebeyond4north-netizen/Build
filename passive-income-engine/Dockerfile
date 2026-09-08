FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY engine.py .
RUN mkdir -p /data
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "engine:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
