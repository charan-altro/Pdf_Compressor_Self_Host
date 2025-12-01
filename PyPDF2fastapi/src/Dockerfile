ARG BASE_IMAGE=python:3.10-slim-bookworm
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="Selfhost PDF Compressor Tool - FastAPI"
ENV PROJECT_NAME="Selfhost PDF Compressor Tool - FastAPI"

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# allow optional Ghostscript install via build-arg (default: true)
ARG INSTALL_GS=true
# option to try installing a newer libpng from backports if available
ARG USE_BACKPORTS=false

# update base packages, try to upgrade libpng if a fixed package is available,
# optionally pull libpng from bookworm-backports, then optionally install ghostscript.
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    if [ "${USE_BACKPORTS}" = "true" ]; then \
        echo "deb http://deb.debian.org/debian bookworm-backports main" > /etc/apt/sources.list.d/bookworm-backports.list; \
        apt-get update; \
        # try to install newer libpng from backports (non-fatal if not available)
        apt-get -t bookworm-backports install -y --no-install-recommends libpng16-16 || true; \
    else \
        # try to upgrade libpng from the regular repos (non-fatal if not available)
        apt-get install --only-upgrade -y --no-install-recommends libpng16-16 || true; \
    fi; \
    if [ "$INSTALL_GS" = "true" ] ; then \
        apt-get install -y --no-install-recommends ghostscript ca-certificates; \
    else \
        echo "Skipping ghostscript install (BUILD ARG INSTALL_GS=false)"; \
    fi; \
    rm -rf /var/lib/apt/lists/*

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
