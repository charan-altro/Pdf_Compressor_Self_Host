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
  echo "Error: set DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD environment variables." >&2
  usage
  exit 2
fi

# login first (required for buildx push to Docker Hub)
printf "%s" "${DOCKERHUB_PASSWORD}" | docker login --username "${DOCKERHUB_USERNAME}" --password-stdin

# prepare tags
FULL_TAG="${IMAGE_NAME}:${TAG}"
TAGS="-t ${FULL_TAG}"
if [ "${TAG}" != "latest" ]; then
  TAGS="${TAGS} -t ${IMAGE_NAME}:latest"
fi

# Use buildx multi-arch build when requested
if [ "${USE_BUILDX}" = "true" ]; then
  if ! docker buildx version >/dev/null 2>&1; then
    echo "Warning: docker buildx not found or not available. Falling back to single-arch docker build."
    USE_BUILDX=false
  fi
fi

if [ "${USE_BUILDX}" = "true" ]; then
  # create / bootstrap builder if requested
  if [ "${CREATE_BUILDER}" = "true" ]; then
    echo "Creating/using buildx builder: ${BUILDER_NAME}"
    # create builder if not exists; --use to switch to it
    docker buildx create --name "${BUILDER_NAME}" --use >/dev/null 2>&1 || docker buildx use "${BUILDER_NAME}" >/dev/null 2>&1 || true
    docker buildx inspect "${BUILDER_NAME}" --bootstrap >/dev/null 2>&1 || true
  fi

  # optional QEMU registration (requires privileged)
  if [ "${REGISTER_QEMU}" = "true" ]; then
    echo "Registering QEMU emulators for multi-arch (requires privileged Docker)"
    docker run --rm --privileged tonistiigi/binfmt:latest --install all || true
  fi

  echo "Building multi-arch image ${IMAGE_NAME} for platforms: ${PLATFORMS}"
  # buildx accepts multiple -t flags; ensure TAGS is expanded
  # shellcheck disable=SC2086
  docker buildx build --platform "${PLATFORMS}" --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" ${TAGS} "${CONTEXT}" --push
  echo "Buildx finished and pushed: ${IMAGE_NAME}:${TAG}"
  exit 0
fi

# Fallback: single-arch build & push (amd64 default) if buildx disabled/unavailable
echo "Building single-arch image ${FULL_TAG} using docker build..."
docker build --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" -t "${FULL_TAG}" "${CONTEXT}"
docker push "${FULL_TAG}"
if [ "${TAG}" != "latest" ]; then
  docker tag "${FULL_TAG}" "${IMAGE_NAME}:latest"
  docker push "${IMAGE_NAME}:latest"
fi

echo "Done. Pushed: ${FULL_TAG}"
