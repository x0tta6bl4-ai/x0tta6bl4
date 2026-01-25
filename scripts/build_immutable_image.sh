#!/bin/bash
# Build immutable Docker image with content-addressable tags
# Usage: ./scripts/build_immutable_image.sh [registry] [image-name]

set -e

REGISTRY="${1:-${CI_REGISTRY:-registry.gitlab.com}}"
IMAGE_NAME="${2:-${CI_REGISTRY_IMAGE:-x0tta6bl4/x0tta6bl4}}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.app}"

# Get commit SHA for content-addressable tag
COMMIT_SHA="${CI_COMMIT_SHA:-$(git rev-parse HEAD)}"
SHORT_SHA="${COMMIT_SHA:0:12}"

# Build image
echo "🔨 Building Docker image..."
docker build -f "$DOCKERFILE" -t "${IMAGE_NAME}:${COMMIT_SHA}" -t "${IMAGE_NAME}:sha256-${SHORT_SHA}" .

# Calculate image digest (content-addressable)
echo "📊 Calculating image digest..."
IMAGE_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "${IMAGE_NAME}:${COMMIT_SHA}" 2>/dev/null || echo "")

if [ -z "$IMAGE_DIGEST" ]; then
    # If digest not available, use SHA256 of image
    IMAGE_DIGEST="${IMAGE_NAME}@sha256:$(docker inspect --format='{{.Id}}' "${IMAGE_NAME}:${COMMIT_SHA}" | cut -d: -f2)"
fi

echo "✅ Image built: ${IMAGE_NAME}:${COMMIT_SHA}"
echo "✅ Content-addressable tag: ${IMAGE_NAME}:sha256-${SHORT_SHA}"
echo "✅ Image digest: ${IMAGE_DIGEST}"

# Sign image with cosign (if available)
if command -v cosign &> /dev/null; then
    if [ -n "$COSIGN_KEY_PATH" ] && [ -f "$COSIGN_KEY_PATH" ]; then
        echo "🔐 Signing image with cosign..."
        cosign sign --key "$COSIGN_KEY_PATH" "${IMAGE_NAME}:${COMMIT_SHA}" || echo "⚠️ Image signing failed (non-critical)"
    else
        echo "⚠️ COSIGN_KEY_PATH not set, skipping image signing"
    fi
else
    echo "⚠️ cosign not available, skipping image signing"
fi

# Export metadata
cat > /tmp/image_metadata.json <<EOF
{
  "image": "${IMAGE_NAME}",
  "tag": "${COMMIT_SHA}",
  "sha256_tag": "sha256-${SHORT_SHA}",
  "digest": "${IMAGE_DIGEST}",
  "commit_sha": "${COMMIT_SHA}",
  "short_sha": "${SHORT_SHA}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "📋 Image metadata saved to /tmp/image_metadata.json"
cat /tmp/image_metadata.json

