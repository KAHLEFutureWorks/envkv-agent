FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Berlin

WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY spike /app/spike
COPY tools /app/tools

RUN addgroup --system envkv && adduser --system --ingroup envkv envkv \
    && mkdir -p /app/data && chown -R envkv:envkv /app/data
USER envkv

EXPOSE 8088
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8088/api/v1/health'))['status']=='ok'"
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8088"]
