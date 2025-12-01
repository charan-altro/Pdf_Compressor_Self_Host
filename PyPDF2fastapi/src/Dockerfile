ARG BASE_IMAGE=python:3.10-slim-bookworm
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="Selfhost PDF Compressor Tool - FastAPI"
ENV PROJECT_NAME="Selfhost PDF Compressor Tool - FastAPI"

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# allow optional Ghostscript install via build-arg (default: true)
ARG INSTALL_GS=true
# choose which Debian suite/repo to use for getting the newest OS packages
# valid values: stable | backports | testing | unstable
# e.g. --build-arg TARGET_SUITE=unstable
ARG TARGET_SUITE=backports

# Prefer TARGET_SUITE for all OS packages by pinning that suite and setting Default-Release.
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    case "${TARGET_SUITE:-}" in \
        backports) ARCH="bookworm-backports"; SOURCELINE="deb http://deb.debian.org/debian bookworm-backports main contrib non-free";; \
        testing)    ARCH="testing";                SOURCELINE="deb http://deb.debian.org/debian testing main contrib non-free";; \
        unstable)   ARCH="unstable";               SOURCELINE="deb http://deb.debian.org/debian unstable main contrib non-free";; \
        stable|*|'') ARCH="";                       SOURCELINE="";; \
    esac; \
    if [ -n "${SOURCELINE}" ]; then echo "${SOURCELINE}" > /etc/apt/sources.list.d/target.list; fi; \
    if [ -n "${ARCH}" ]; then \
        cat > /etc/apt/preferences.d/99target <<'EOF'\nPackage: *\nPin: release a=${ARCH}\nPin-Priority: 990\nEOF\n        echo "APT::Default-Release \"${ARCH}\";" > /etc/apt/apt.conf.d/99defaultrelease; \
    fi; \
    apt-get update; \
    if [ -n "${ARCH}" ]; then \
        apt-get -t "${ARCH}" dist-upgrade -y || apt-get -t "${ARCH}" upgrade -y || true; \
    else \
        apt-get dist-upgrade -y || apt-get upgrade -y || true; \
    fi; \
    if [ "${INSTALL_GS}" = "true" ]; then \
        apt-get update; \
        apt-get install -y --no-install-recommends ghostscript ca-certificates || true; \
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
