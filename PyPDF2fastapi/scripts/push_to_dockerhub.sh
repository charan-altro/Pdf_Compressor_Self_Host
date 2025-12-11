#!/usr/bin/env bash
set -euo pipefail

# Variables
IMAGE_NAME="selfhost-pdf-compressor" # Updated to match the repository name
DOCKERHUB_USERNAME="charankumarbs" # Replace with your Docker Hub username
TAG="latest"
PLATFORMS="linux/amd64,linux/arm64"

# Functions
usage() {
  echo "Usage: $0 [--multi-arch] [--tag <tag>] [--username <dockerhub-username>]"
  echo "  --multi-arch       Build and push multi-architecture images (default: false)"
  echo "  --tag <tag>        Specify the tag for the image (default: latest)"
  echo "  --username <name>  Specify the Docker Hub username (default: charankumarbs)"
  exit 1
}

# Parse arguments
MULTI_ARCH=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --multi-arch)
      MULTI_ARCH=true
      shift
      ;;
    --tag)
      TAG="$2"
      shift 2
      ;;
    --username)
      DOCKERHUB_USERNAME="$2"
      shift 2
      ;;
    *)
      usage
      ;;
  esac
done

# Ensure Docker Hub username is set
if [[ -z "$DOCKERHUB_USERNAME" ]]; then
  echo "Error: Docker Hub username is not set. Use --username to specify it."
  exit 1
fi

# Full image name
FULL_IMAGE_NAME="${DOCKERHUB_USERNAME}/${IMAGE_NAME}:${TAG}"

# Login to Docker Hub
echo "Logging in to Docker Hub..."
docker login --username "$DOCKERHUB_USERNAME"

# Build and push the image
if [ "$MULTI_ARCH" = true ]; then
  echo "Building and pushing multi-architecture image for platforms: $PLATFORMS"
  docker buildx create --use || true
  docker buildx build --platform "$PLATFORMS" -t "$FULL_IMAGE_NAME" -f src/Dockerfile ./src --push
else
  echo "Building and pushing single-architecture image..."
  docker build -f src/Dockerfile -t "$FULL_IMAGE_NAME" ./src
  docker push "$FULL_IMAGE_NAME"
fi

echo "Image pushed successfully: $FULL_IMAGE_NAME"
