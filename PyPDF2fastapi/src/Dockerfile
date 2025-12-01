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
# option to compile and install patched libpng from source (recommended when distro has no fix)
ARG LIBPNG_PATCH=true
ARG LIBPNG_VERSION=1.6.51

# update base packages, try to upgrade libpng if a fixed package is available,
# optionally pull libpng from bookworm-backports, then optionally install ghostscript.
RUN set -eux; \
    apt-get update; \
    apt-get upgrade -y; \
    if [ "${USE_BACKPORTS}" = "true" ]; then \
        echo "deb http://deb.debian.org/debian bookworm-backports main" > /etc/apt/sources.list.d/bookworm-backports.list; \
        apt-get update; \
        apt-get -t bookworm-backports install -y --no-install-recommends libpng16-16 || true; \
    else \
        apt-get install --only-upgrade -y --no-install-recommends libpng16-16 || true; \
    fi; \
    if [ "${LIBPNG_PATCH}" = "true" ]; then \
        echo "Building libpng ${LIBPNG_VERSION} from source to ensure patched libpng is installed"; \
        # install minimal build deps
        apt-get install -y --no-install-recommends build-essential wget ca-certificates zlib1g-dev xz-utils; \
        # determine download URL: support LIBPNG_VERSION=latest or an explicit version
        if [ "${LIBPNG_VERSION}" = "latest" ]; then \
            echo "Resolving latest libpng release from SourceForge..."; \
            FILE=$(wget -qO- https://download.sourceforge.net/libpng/ | grep -oE 'libpng-[0-9]+(\\.[0-9]+){1,2}\\.tar\\.(xz|gz)' | sort -V | tail -n1 || true); \
            if [ -n "${FILE}" ]; then \
                URL="https://download.sourceforge.net/libpng/${FILE}"; \
                OUT="/tmp/${FILE}"; \
            else \
                echo "Warning: could not determine latest libpng; falling back to ${LIBPNG_VERSION} naming"; \
                URL="https://download.sourceforge.net/libpng/libpng-${LIBPNG_VERSION}.tar.xz"; \
                OUT="/tmp/libpng-${LIBPNG_VERSION}.tar.xz"; \
            fi; \
        else \
            FILE="libpng-${LIBPNG_VERSION}.tar.xz"; \
            URL="https://download.sourceforge.net/libpng/${FILE}"; \
            OUT="/tmp/${FILE}"; \
        fi; \
        echo "Downloading ${URL} ..."; \
        wget -qO "${OUT}" "${URL}"; \
        case "${OUT}" in \
            *.tar.xz) tar -xf "${OUT}" -C /tmp ;; \
            *.tar.gz) tar -xzf "${OUT}" -C /tmp ;; \
            *.tgz)    tar -xzf "${OUT}" -C /tmp ;; \
            *) echo "Unknown archive format: ${OUT}" >&2; exit 1 ;; \
        esac; \
        # find extracted dir (prefix libpng-<ver>)
        DIR=$(basename "${OUT}" | sed -E 's/^(libpng-[0-9.]+)\\.tar\\.(xz|gz|tgz)$/\\1/'); \
        cd /tmp/${DIR} && ./configure --prefix=/usr/local && make -j"$(nproc)" && make install; \
        ldconfig; \
        rm -rf /tmp/libpng*; \
        # remove build deps to shrink image
        apt-get purge -y build-essential wget xz-utils; \
        apt-get autoremove -y; \
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
