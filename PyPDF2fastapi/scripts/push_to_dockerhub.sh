#!/bin/sh
set -eu

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
  BUILD_NETWORK         ${BUILD_NETWORK:-host}   # use 'host' to help DNS during build; set to 'default' or '' to skip flag
  BUILD_RETRIES         ${BUILD_RETRIES:-3}      # retry build this many times on failure

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
: "${BUILD_NETWORK:=host}"     # use 'host' to help DNS during build; set to 'default' or '' to skip flag
: "${BUILD_RETRIES:=3}"        # retry build this many times on failure

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

FULL_TAG="${IMAGE_NAME}:${TAG}"

# prepare network args (omit if empty or set to 'default' to use Docker default)
NETWORK_ARGS=""
if [ -n "${BUILD_NETWORK}" ] && [ "${BUILD_NETWORK}" != "default" ]; then
  NETWORK_ARGS="--network ${BUILD_NETWORK}"
fi

echo "Building image ${FULL_TAG} using ${DOCKERFILE} (INSTALL_GS=${INSTALL_GS})..."
echo "Build network: ${BUILD_NETWORK:-default}, retries: ${BUILD_RETRIES}"

# build with retries to tolerate transient DNS/network failures
i=1
while [ "$i" -le "${BUILD_RETRIES}" ]; do
  echo "Build attempt ${i}/${BUILD_RETRIES}..."
  if docker build ${NETWORK_ARGS} --build-arg INSTALL_GS="${INSTALL_GS}" -f "${DOCKERFILE}" -t "${FULL_TAG}" "${CONTEXT}"; then
    break
  fi
  if [ "$i" -lt "${BUILD_RETRIES}" ]; then
    echo "Build failed, retrying in 5s..."
    sleep 5
  else
    echo "Build failed after ${BUILD_RETRIES} attempts." >&2
    exit 1
  fi
  i=$((i+1))
done

echo "Logging into Docker Hub as ${DOCKERHUB_USERNAME}..."
# pass password via stdin to avoid leaking in process list
printf "%s" "${DOCKERHUB_PASSWORD}" | docker login --username "${DOCKERHUB_USERNAME}" --password-stdin

echo "Pushing ${FULL_TAG}..."
docker push "${FULL_TAG}"

# Optionally also push 'latest' when TAG is something else
if [ "${TAG}" != "latest" ]; then
  echo "Also tagging and pushing 'latest' -> ${IMAGE_NAME}:latest"
  docker tag "${FULL_TAG}" "${IMAGE_NAME}:latest"
  docker push "${IMAGE_NAME}:latest"
fi

echo "Done. Pushed: ${FULL_TAG}"
