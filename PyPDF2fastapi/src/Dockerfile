FROM python:3.10-slim-bullseye

LABEL org.opencontainers.image.title="Selfhost PDF Compressor Tool - FastAPI"
ENV PROJECT_NAME="Selfhost PDF Compressor Tool - FastAPI"

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# allow optional Ghostscript install via build-arg (default: true)
ARG INSTALL_GS=true

# install ghostscript only when requested; keep layer small
RUN if [ "$INSTALL_GS" = "true" ] ; then \
      apt-get update && \
      apt-get install -y --no-install-recommends ghostscript ca-certificates && \
      rm -rf /var/lib/apt/lists/* ; \
    else \
      echo "Skipping ghostscript install (BUILD ARG INSTALL_GS=false)"; \
    fi

COPY requirements.txt /usr/src/app/requirements.txt
RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r /usr/src/app/requirements.txt

COPY . /usr/src/app/

# create a non-root user for better security
RUN useradd --create-home --shell /bin/bash appuser \
 && chown -R appuser:appuser /usr/src/app

# switch into the 'src' directory so 'app' package is on sys.path
WORKDIR /usr/src/app/src

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
