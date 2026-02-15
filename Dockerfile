# =============================================================================
# x0tta6bl4 Node — Multi-stage Docker Build
# Post-quantum mesh node with liboqs, GraphSAGE (CPU), FastAPI
# =============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Build liboqs from source + install Python deps into a virtualenv
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ARG LIBOQS_VERSION=0.12.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git libssl-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Build liboqs (shared lib)
WORKDIR /tmp
RUN git clone --depth 1 --branch "${LIBOQS_VERSION}" \
    https://github.com/open-quantum-safe/liboqs.git && \
    cmake -S liboqs -B liboqs/build \
    -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_INSTALL_PREFIX=/usr/local && \
    cmake --build liboqs/build --parallel "$(nproc)" && \
    cmake --install liboqs/build && \
    rm -rf /tmp/liboqs

# Create virtualenv for clean site-packages copy
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install torch CPU-only first (saves ~3GB vs CUDA)
RUN pip install --no-cache-dir \
    torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu

# Copy only dependency metadata for layer caching
WORKDIR /build
COPY pyproject.toml ./
COPY requirements.txt ./

# Install runtime deps (core + monitoring, no dev/bots/lora)
# torch already installed above from CPU-only index — skip it here
RUN grep -iv '^torch' requirements.txt > /tmp/requirements-no-torch.txt && \
    pip install --no-cache-dir -r /tmp/requirements-no-torch.txt && \
    pip install --no-cache-dir \
    prometheus-client==0.23.1 \
    opentelemetry-api==1.38.0 \
    opentelemetry-sdk==1.38.0 \
    opentelemetry-exporter-otlp-proto-grpc==1.38.0 \
    opentelemetry-semantic-conventions==0.59b0 \
    liboqs-python

# ---------------------------------------------------------------------------
# Stage 2: Minimal runtime image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

LABEL maintainer="x0tta6bl4 Team" \
    version="3.2.1" \
    description="Self-healing mesh node with post-quantum cryptography"

# Runtime system deps (curl for healthcheck, libssl for crypto)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy liboqs shared libraries
COPY --from=builder /usr/local/lib/liboqs* /usr/local/lib/
COPY --from=builder /usr/local/include/oqs /usr/local/include/oqs
RUN ldconfig

# Copy Python virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Non-root user
RUN useradd -m -u 1000 -s /bin/bash x0tta6bl4 && \
    mkdir -p /app/data /app/logs && \
    chown -R x0tta6bl4:x0tta6bl4 /app

WORKDIR /app

# Copy only application source
COPY --chown=x0tta6bl4:x0tta6bl4 src/ ./src/

USER x0tta6bl4

# API port
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["uvicorn", "src.core.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
