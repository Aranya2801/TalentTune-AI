FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TALENTTUNE_DB=/data/talenttune.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY talenttune ./talenttune
COPY web ./web
COPY examples ./examples

RUN mkdir -p /data && useradd -m app && chown app /data
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "talenttune.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
