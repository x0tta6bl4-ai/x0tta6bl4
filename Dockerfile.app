# Dockerfile for x0tta6bl4 FastAPI application

# Stage 1: Builder
FROM python:3.12-slim as builder

# Metadata
LABEL maintainer="x0tta6bl4 Team <contact@x0tta6bl4.net>"
LABEL version="3.2.0"
LABEL description="Self-healing mesh network with post-quantum cryptography"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH="/root/.local/bin:$PATH"

# Install system dependencies required for building some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libc6-dev \
    libffi-dev \
    libssl-dev \
    curl \
    cmake \
    git \
    pkg-config \
    libpq-dev \
    ninja-build \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone and build liboqs from source
RUN git clone --depth 1 --branch 0.14.0 https://github.com/open-quantum-safe/liboqs.git && \
    cmake -S liboqs -B liboqs/build -DBUILD_SHARED_LIBS=ON && \
    cmake --build liboqs/build --parallel 8 && \
    cmake --build liboqs/build --target install

# Copy requirements files
COPY requirements.txt .
COPY requirements-dev.txt .
COPY requirements.min.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.min.txt && \
    pip install -r requirements-dev.txt

RUN pip wheel --wheel-dir=/wheelhouse -r requirements.min.txt -r requirements-dev.txt

# Stage 2: Production
FROM python:3.12-slim as production

# Metadata
LABEL maintainer="x0tta6bl4 Team <contact@x0tta6bl4.net>"
LABEL version="3.2.0"
LABEL description="Self-healing mesh network with post-quantum cryptography"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install *only* runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app /app/data /app/logs && \
    chown -R appuser:appuser /app

# Set working directory
WORKDIR /app

# Copy only production dependencies from builder stage
COPY --from=builder /wheelhouse /wheelhouse
COPY requirements.min.txt .
RUN pip install --no-index --find-links=/wheelhouse -r requirements.min.txt

# Copy application code
COPY --chown=appuser:appuser src/ ./src

# Copy the compiled liboqs shared library from the builder stage
COPY --from=builder /usr/local/lib/liboqs.so* /usr/local/lib/
RUN ldconfig

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8080 8081 4001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run with read-only filesystem
CMD ["uvicorn", "src.core.app:app", "--host", "0.0.0.0", "--port", "8080"]
