FROM python:3-slim-bookworm

LABEL org.opencontainers.image.title="Selfhost PDF Compressor Tool - FastAPI"
ENV PROJECT_NAME="Selfhost PDF Compressor Tool - FastAPI"

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Select PDF tool: set INSTALL_GS=true to install Ghostscript, otherwise qpdf will be used.
ARG INSTALL_GS=true

# copy only requirements first to leverage Docker layer cache
COPY requirements.txt /usr/src/app/requirements.txt

# install ghostscript only when requested; keep layer small
RUN set -eux; \
    for i in 1 2 3; do \
        apt-get update && break || { echo "Retrying apt-get update... ($i/3)"; sleep 5; }; \
    done; \
    if [ "$INSTALL_GS" = "true" ] ; then \
      apt-get install -y --no-install-recommends ghostscript ca-certificates && \
      rm -rf /var/lib/apt/lists/* ; \
    else \
      echo "Skipping ghostscript install (BUILD ARG INSTALL_GS=false)"; \
    fi

# copy app sources
COPY . /usr/src/app/

# ensure pip is up-to-date and install Python deps (use python -m pip to avoid wrong pip)
RUN python -m pip install --upgrade pip setuptools wheel \
 && python -m pip install --no-cache-dir -r requirements.txt

# create non-root user
RUN if command -v adduser >/dev/null 2>&1; then \
      adduser --disabled-password --gecos "" --uid 1000 appuser; \
    else \
      useradd -u 1000 -M -s /usr/sbin/nologin appuser; \
    fi \
    && chown -R appuser:appuser /usr/src/app

USER appuser
# ensure app runs with python -m so uvicorn is loaded as a module
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]