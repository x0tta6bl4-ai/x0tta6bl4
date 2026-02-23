#!/bin/bash
# Fixed Deployer
docker build -t x0tta6bl4-landing:latest -f marketing/landing/Dockerfile.landing .
docker stop x0tta6bl4-landing-container 2>/dev/null || true
docker rm x0tta6bl4-landing-container 2>/dev/null || true
docker run -d --name x0tta6bl4-landing-container --restart always -p 8081:80 x0tta6bl4-landing:latest
echo "✅ Landing page fix-deployed on http://localhost:8081"
