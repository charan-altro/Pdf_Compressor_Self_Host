FROM python:3.10-alpine3.18

LABEL org.opencontainers.image.title="Selfhost PDF Compressor Tool - FastAPI"
ENV PROJECT_NAME="Selfhost PDF Compressor Tool - FastAPI"

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG INSTALL_GS=true

COPY requirements.txt /usr/src/app/requirements.txt

RUN apk add --no-cache ca-certificates \
 && apk add --no-cache --virtual .build-deps gcc musl-dev libffi-dev openssl-dev zlib-dev jpeg-dev \
 && if [ "${INSTALL_GS}" = "true" ]; then apk add --no-cache ghostscript; else apk add --no-cache qpdf; fi \
 && pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r /usr/src/app/requirements.txt \
 && apk del .build-deps \
 && rm -rf /var/cache/apk/*

COPY . /usr/src/app/

RUN adduser -D -u 1000 appuser \
 && chown -R appuser:appuser /usr/src/app

USER appuser

WORKDIR /usr/src/app/src

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
