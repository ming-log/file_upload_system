FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG http_proxy
ARG https_proxy
ARG no_proxy

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app

RUN HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" NO_PROXY="$NO_PROXY" \
    http_proxy="$http_proxy" https_proxy="$https_proxy" no_proxy="$no_proxy" \
    pip install --no-cache-dir --upgrade pip \
    && HTTP_PROXY="$HTTP_PROXY" HTTPS_PROXY="$HTTPS_PROXY" NO_PROXY="$NO_PROXY" \
    http_proxy="$http_proxy" https_proxy="$https_proxy" no_proxy="$no_proxy" \
    pip install --no-cache-dir .

RUN mkdir -p /data/uploaded_files

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
