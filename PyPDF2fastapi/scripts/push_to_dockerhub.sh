#!/usr/bin/env bash
set -euo pipefail

# Minimal usage/help
usage() {
  cat <<EOF
Usage: DOCKERHUB_USERNAME=... DOCKERHUB_PASSWORD=... ./scripts/push_to_dockerhub.sh [options]

Environment variables (defaults shown):
  IMAGE_NAME            ${IMAGE_NAME:-charankumarbs/selfhost-pdf-compressor}
  TAG                   ${TAG:-latest}
  INSTALL_GS            ${INSTALL_GS:-true}   # build-arg passed to Docker
  DOCKERFILE            ${DOCKERFILE:-src/Dockerfile}
  CONTEXT               ${CONTEXT:-.}

Examples:
  DOCKERHUB_USERNAME=user DOCKERHUB_PASSWORD=pass ./scripts/push_to_dockerhub.sh
  IMAGE_NAME=me/repo TAG=v1.2.3 ./scripts/push_to_dockerhub.sh
EOF
}

# defaults (can be overridden by env)
: "${IMAGE_NAME:=charankumarbs/selfhost-pdf-compressor}"
: "${TAG:=latest}"
: "${INSTALL_GS:=true}"
: "${DOCKERFILE:=src/Dockerfile}"
: "${CONTEXT:=.}"

# if user asked for help
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

# check docker
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker CLI not found in PATH." >&2
  exit 2
fi

# require credentials in env
if [[ -z "${DOCKERHUB_USERNAME:-}" || -z "${DOCKERHUB_PASSWORD:-}" ]]; then
  echo "Error: set DOCKERHUB_USERNAME and DOCKERHUB_PASSWORD environment variables." >&2
  usage
  exit 2
fi

FULL_TAG="${IMAGE_NAME}:${TAG}"

echo "Building image ${FULL_TAG} using ${DOCKERFILE} (INSTALL_GS=${INSTALL_GS})..."
docker build --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" -t "${FULL_TAG}" "${CONTEXT}"

echo "Logging into Docker Hub as ${DOCKERHUB_USERNAME}..."
# pass password via stdin to avoid leaking in process list
printf "%s" "${DOCKERHUB_PASSWORD}" | docker login --username "${DOCKERHUB_USERNAME}" --password-stdin

echo "Pushing ${FULL_TAG}..."
docker push "${FULL_TAG}"

# Optionally also push 'latest' when TAG is something else
if [[ "${TAG}" != "latest" ]]; then
  echo "Also tagging and pushing 'latest' -> ${IMAGE_NAME}:latest"
  docker tag "${FULL_TAG}" "${IMAGE_NAME}:latest"
  docker push "${IMAGE_NAME}:latest"
fi

echo "Done. Pushed: ${FULL_TAG}"
