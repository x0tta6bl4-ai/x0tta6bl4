#!/bin/bash
# Build Docker image for x0tta6bl4 v3.4.0
# Usage: ./scripts/build_docker_image.sh [tag]

set -e

VERSION="${1:-3.4.0}"
IMAGE_NAME="x0tta6bl4"
FULL_TAG="${IMAGE_NAME}:${VERSION}"

echo "🔨 Building Docker image: ${FULL_TAG}"
echo "=================================="

# Check disk space
DISK_AVAILABLE=$(df -h / | tail -1 | awk '{print $4}')
echo "📊 Disk space available: ${DISK_AVAILABLE}"

# Check Docker space
echo "📊 Docker disk usage:"
docker system df

# Build image
echo ""
echo "🚀 Starting build..."
docker build \
  --tag "${FULL_TAG}" \
  --tag "${IMAGE_NAME}:latest" \
  --file Dockerfile \
  --progress=plain \
  .

# Verify image
echo ""
echo "✅ Build complete! Verifying image..."
docker images | grep "${IMAGE_NAME}" | grep -E "${VERSION}|latest"

echo ""
echo "📦 Image size:"
docker images "${FULL_TAG}" --format "{{.Size}}"

echo ""
echo "✅ Docker image built successfully: ${FULL_TAG}"
echo "📝 Next step: Load into kind cluster"
echo "   kind load docker-image ${FULL_TAG} --name x0tta6bl4-staging"


