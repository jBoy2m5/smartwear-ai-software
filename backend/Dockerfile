FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SMARTWEAR_ENVIRONMENT=production

WORKDIR /app

RUN addgroup --system smartwear && adduser --system --ingroup smartwear smartwear

COPY requirements.txt /app/backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install --requirement /app/backend/requirements.txt

COPY . /app/backend

RUN mkdir -p /app/backend/data /app/backend/artifacts \
    && chown -R smartwear:smartwear /app/backend

USER smartwear

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

