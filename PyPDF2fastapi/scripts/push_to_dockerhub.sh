#!/bin/sh
set -eu

# Minimal usage/help
usage() {
  cat <<EOF
Usage: DOCKERHUB_USERNAME=... DOCKERHUB_PASSWORD=... ./scripts/push_to_dockerhub.sh

Environment variables (defaults shown):
  IMAGE_NAME        ${IMAGE_NAME:-charankumarbs/selfhost-pdf-compressor}
  TAG               ${TAG:-latest}
  INSTALL_GS        ${INSTALL_GS:-true}
  DOCKERFILE        ${DOCKERFILE:-src/Dockerfile}
  CONTEXT           ${CONTEXT:-.}
  PLATFORMS         ${PLATFORMS:-linux/amd64,linux/arm64}
  USE_BUILDX        ${USE_BUILDX:-true}
  BUILDER_NAME      ${BUILDER_NAME:-multi-builder}
  CREATE_BUILDER    ${CREATE_BUILDER:-true}
  REGISTER_QEMU     ${REGISTER_QEMU:-false}   # set true on supported hosts to enable emulation
Examples:
  DOCKERHUB_USERNAME=user DOCKERHUB_PASSWORD=pass ./scripts/push_to_dockerhub.sh
  PLATFORMS=linux/amd64,linux/arm64 TAG=v1.2.3 ./scripts/push_to_dockerhub.sh
EOF
}

# defaults (can be overridden by env)
: "${IMAGE_NAME:=charankumarbs/selfhost-pdf-compressor}"
: "${TAG:=latest}"
: "${INSTALL_GS:=true}"
: "${DOCKERFILE:=src/Dockerfile}"
: "${CONTEXT:=.}"
: "${PLATFORMS:=linux/amd64,linux/arm64}"
: "${USE_BUILDX:=true}"
: "${BUILDER_NAME:=multi-builder}"
: "${CREATE_BUILDER:=true}"
: "${REGISTER_QEMU:=false}"

# New options to control buildx networking and retries
: "${BUILD_NETWORK:=host}"               # network mode passed to buildx build --network (e.g. host or default)
: "${DRIVER_OPTS_NETWORK:=host}"         # network passed as --driver-opt network=... when creating docker-container builder
: "${CREATE_BUILDER_DRIVER_OPTS:=true}"  # create builder with driver-opts (network host) when true
: "${BUILD_RETRIES:=3}"                  # retry buildx build this many times on transient failures
: "${BUILD_RETRY_SLEEP:=5}"              # seconds to wait between retries

# if user asked for help
if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

# check docker
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker CLI not found in PATH." >&2
  exit 2
fi

# require credentials in env
if [ -z "${DOCKERHUB_USERNAME:-}" ] || [ -z "${DOCKERHUB_PASSWORD:-}" ]; then
  echo "Error: set DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD" >&2
  exit 2
fi
printf "%s" "${DOCKERHUB_PASSWORD}" | docker login --username "${DOCKERHUB_USERNAME}" --password-stdin

FULL_TAG="${IMAGE_NAME}:${TAG}"
TAGS="-t ${FULL_TAG}"
if [ "${TAG}" != "latest" ]; then
  TAGS="${TAGS} -t ${IMAGE_NAME}:latest"
fi

# detect buildx availability
if [ "${USE_BUILDX}" = "true" ]; then
  if ! docker buildx version >/dev/null 2>&1; then
    echo "Warning: docker buildx not available. Falling back to single-arch docker build."
    USE_BUILDX=false
  fi
fi

if [ "${USE_BUILDX}" = "true" ]; then
  if [ "${CREATE_BUILDER}" = "true" ]; then
    echo "Creating/using buildx builder: ${BUILDER_NAME}"
    if [ "${CREATE_BUILDER_DRIVER_OPTS}" = "true" ]; then
      # try creating a docker-container builder with network driver-opt (helps DNS resolution)
      docker buildx create --name "${BUILDER_NAME}" --driver docker-container --driver-opt network="${DRIVER_OPTS_NETWORK}" --use >/dev/null 2>&1 || true
      # ensure builder is bootstrapped
      docker buildx inspect "${BUILDER_NAME}" --bootstrap >/dev/null 2>&1 || true
    else
      docker buildx create --name "${BUILDER_NAME}" --use >/dev/null 2>&1 || docker buildx use "${BUILDER_NAME}" >/dev/null 2>&1 || true
      docker buildx inspect "${BUILDER_NAME}" --bootstrap >/dev/null 2>&1 || true
    fi
  fi

  if [ "${REGISTER_QEMU}" = "true" ]; then
    echo "Registering QEMU emulators for multi-arch (requires privileged Docker)"
    docker run --rm --privileged tonistiigi/binfmt:latest --install all || true
  fi

  echo "Building multi-arch image ${IMAGE_NAME} for platforms: ${PLATFORMS} (network=${BUILD_NETWORK})"

  # retry loop for buildx build (handles transient DNS/registry issues)
  attempt=1
  while [ "${attempt}" -le "${BUILD_RETRIES}" ]; do
    echo "Buildx attempt ${attempt}/${BUILD_RETRIES}..."
    # shellcheck disable=SC2086
    if docker buildx build --platform "${PLATFORMS}" --network "${BUILD_NETWORK}" --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" ${TAGS} "${CONTEXT}" --push; then
      echo "Buildx succeeded."
      break
    fi
    echo "Buildx build failed on attempt ${attempt}."
    attempt=$((attempt + 1))
    if [ "${attempt}" -le "${BUILD_RETRIES}" ]; then
      echo "Retrying in ${BUILD_RETRY_SLEEP}s..."
      sleep "${BUILD_RETRY_SLEEP}"
    else
      echo "Buildx build failed after ${BUILD_RETRIES} attempts." >&2
      exit 1
    fi
  done

  exit 0
fi

# Fallback to single-arch docker build
echo "Building single-arch image ${FULL_TAG} using docker build..."
docker build --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" -t "${FULL_TAG}" "${CONTEXT}"
docker push "${FULL_TAG}"
if [ "${TAG}" != "latest" ]; then
  docker tag "${FULL_TAG}" "${IMAGE_NAME}:latest"
  docker push "${IMAGE_NAME}:latest"
fi

echo "Done. Pushed: ${FULL_TAG}"
