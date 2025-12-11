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
  REGISTER_QEMU     ${REGISTER_QEMU:-false}
  BUILD_NETWORK     ${BUILD_NETWORK:-host}
  BUILD_RETRIES     ${BUILD_RETRIES:-3}
  FALLBACK_SINGLE   ${FALLBACK_SINGLE:-true}   # when buildx fails, try a single-arch docker build & push
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
: "${BUILD_NETWORK:=host}"
: "${BUILD_RETRIES:=3}"
: "${BUILD_RETRY_SLEEP:=5}"
: "${FALLBACK_SINGLE:=true}"

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
    docker buildx create --name "${BUILDER_NAME}" --driver docker-container --driver-opt network="${BUILD_NETWORK}" --use >/dev/null 2>&1 || true
    docker buildx inspect "${BUILDER_NAME}" --bootstrap >/dev/null 2>&1 || true
  fi

  if [ "${REGISTER_QEMU}" = "true" ]; then
    echo "Registering QEMU emulators for multi-arch (requires privileged Docker)"
    docker run --rm --privileged tonistiigi/binfmt:latest --install all || true
  fi

  echo "Building multi-arch image ${IMAGE_NAME} for platforms: ${PLATFORMS} (network=${BUILD_NETWORK})"

  # retry loop for buildx build (handles transient DNS/registry issues)
  attempt=1
  buildx_success=0
  while [ "${attempt}" -le "${BUILD_RETRIES}" ]; do
    echo "Buildx attempt ${attempt}/${BUILD_RETRIES}..."
    # shellcheck disable=SC2086
    if docker buildx build --platform "${PLATFORMS}" --network "${BUILD_NETWORK}" --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" ${TAGS} "${CONTEXT}" --push; then
      buildx_success=1
      echo "Buildx multi-arch build succeeded."
      break
    fi
    echo "Buildx build failed on attempt ${attempt}."
    attempt=$((attempt + 1))
    if [ "${attempt}" -le "${BUILD_RETRIES}" ]; then
      echo "Retrying in ${BUILD_RETRY_SLEEP}s..."
      sleep "${BUILD_RETRY_SLEEP}"
    fi
  done

  if [ "${buildx_success}" -eq 1 ]; then
    exit 0
  fi

  # Diagnostics and fallback
  echo "Buildx multi-arch build failed after ${BUILD_RETRIES} attempts."
  echo "Common causes: DNS/network issues reaching registry-1.docker.io from the builder container."
  echo "Quick checks you can run on the host:"
  echo "  - curl -v https://registry-1.docker.io/v2/   # check host reachability"
  echo "  - docker run --rm --network host busybox nslookup registry-1.docker.io   # check DNS from container (may require pull)"
  echo "If you are behind a proxy set HTTP_PROXY/HTTPS_PROXY env vars before running the script."
  echo "You can also try BUILD_NETWORK=default or CREATE_BUILDER=false to avoid docker-container driver networking."
  if [ "${FALLBACK_SINGLE}" = "true" ]; then
    echo "Falling back to a single-arch build for the host architecture (so you still get an image pushed)."
    echo "Note: this will NOT produce a multi-arch image; use buildx on a machine with proper network access for multi-arch."
    # perform single-arch build & push
    docker build --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" -t "${FULL_TAG}" "${CONTEXT}"
    echo "Pushing ${FULL_TAG}..."
    docker push "${FULL_TAG}"
    if [ "${TAG}" != "latest" ]; then
      docker tag "${FULL_TAG}" "${IMAGE_NAME}:latest"
      docker push "${IMAGE_NAME}:latest"
    fi
    echo "Single-arch image pushed: ${FULL_TAG}"
    exit 0
  else
    echo "FALLBACK_SINGLE is disabled. Exiting with error."
    exit 1
  fi
fi

# Fallback to single-arch build when buildx disabled/unavailable
echo "Building single-arch image ${FULL_TAG} using docker build..."
docker build --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" -t "${FULL_TAG}" "${CONTEXT}"
docker push "${FULL_TAG}"
if [ "${TAG}" != "latest" ]; then
  docker tag "${FULL_TAG}" "${IMAGE_NAME}:latest"
  docker push "${IMAGE_NAME}:latest"
fi

echo "Done. Pushed: ${FULL_TAG}"
