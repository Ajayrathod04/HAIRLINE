FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
# requirements.lock.txt (exact pins from scripts/freeze_deps.sh) is used when present; the [t] glob keeps COPY valid if absent
COPY requirements.txt requirements-aws.txt requirements.lock.tx[t] ./
RUN if [ -f requirements.lock.txt ]; then pip install -r requirements.lock.txt -r requirements-aws.txt; else pip install -r requirements-aws.txt; fi
COPY . .
RUN useradd -m hl && mkdir -p data && chown -R hl /app
USER hl
ENV HOST=0.0.0.0 PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/api/health',timeout=4)"
CMD ["gunicorn","-w","2","--threads","2","-b","0.0.0.0:8080","--timeout","90","hairline.wsgi:app"]
