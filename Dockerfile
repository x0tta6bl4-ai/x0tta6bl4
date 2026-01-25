# Stage 1: Builder
FROM python:3.11-slim as builder

# Metadata
LABEL maintainer="x0tta6bl4 Team <contact@x0tta6bl4.net>"
LABEL version="3.4.0"
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
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Clone and build liboqs from source (pinned version to match liboqs-python 0.14.1)
RUN git clone --depth 1 --branch 0.14.0 https://github.com/open-quantum-safe/liboqs.git && \
    cmake -S liboqs -B liboqs/build -DBUILD_SHARED_LIBS=ON && \
    cmake --build liboqs/build --parallel 8 && \
    cmake --build liboqs/build --target install

# Copy requirements files
COPY requirements.txt .
COPY requirements-dev.txt .

# Install Python dependencies (including dev dependencies for potential testing in this stage)
RUN pip install torch==2.9.0 --index-url https://download.pytorch.org/whl/cpu && \
    pip install pyg_lib torch_scatter torch_sparse torch_cluster torch_spline_conv -f https://data.pyg.org/whl/torch-2.9.0+cpu.html

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install -r requirements-dev.txt

RUN pip wheel --wheel-dir=/wheelhouse -r requirements.txt -r requirements-dev.txt

# Stage 2: Production
FROM python:3.11-slim as production

# Metadata
LABEL maintainer="x0tta6bl4 Team <contact@x0tta6bl4.net>"
LABEL version="3.4.0"
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
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheelhouse -r requirements.txt
COPY requirements.txt .

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
    CMD curl -f http://localhost:8080/api/v1/health || exit 1

# Default command
CMD ["python", "-m", "src.core.app"]