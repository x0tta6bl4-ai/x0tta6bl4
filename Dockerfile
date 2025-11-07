# Multi-stage build for x0tta6bl4 mesh node
# Base: Python 3.12 + Yggdrasil mesh networking

FROM python:3.12-slim AS base

# Install system dependencies (Yggdrasil, curl for health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    lsb-release \
    ca-certificates \
    iproute2 \
    iptables \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Install Yggdrasil from GitHub releases (.deb package)
RUN YGGDRASIL_VERSION=0.5.5 \
    && curl -fsSL -o /tmp/yggdrasil.deb "https://github.com/yggdrasil-network/yggdrasil-go/releases/download/v${YGGDRASIL_VERSION}/yggdrasil-${YGGDRASIL_VERSION}-amd64.deb" \
    && dpkg -i /tmp/yggdrasil.deb \
    && rm /tmp/yggdrasil.deb

# Create app user (non-root for security)
RUN useradd -m -s /bin/bash x0tta6bl4 && \
    usermod -aG sudo x0tta6bl4 && \
    echo "x0tta6bl4 ALL=(ALL) NOPASSWD: /usr/bin/yggdrasilctl" > /etc/sudoers.d/x0tta6bl4

WORKDIR /app

# Copy Python dependencies and install (caching layer)
COPY requirements.txt requirements.consolidated.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY src/ ./src/
COPY pyproject.toml pytest.ini README.md LICENSE* ./

# Install package in editable mode
RUN pip install -e .

# Create Yggdrasil config directory
RUN mkdir -p /etc/yggdrasil /var/run/yggdrasil /var/log/yggdrasil && \
    chown -R x0tta6bl4:x0tta6bl4 /etc/yggdrasil /var/run/yggdrasil /var/log/yggdrasil

# Switch to app user
USER x0tta6bl4

# Expose ports: 8000 (API), 9090 (Prometheus metrics)
EXPOSE 8000 9090

# Health check: FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint script will:
# 1. Generate Yggdrasil config with peer connections
# 2. Start Yggdrasil daemon
# 3. Launch FastAPI server
COPY docker-entrypoint.sh /usr/local/bin/
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["x0tta6bl4-server"]
