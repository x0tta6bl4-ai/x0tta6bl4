# Dockerfile for x0tta6bl4 FastAPI application

# Stage 1: Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for liboqs compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    cmake \
    ninja-build \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install liboqs from source (before Python packages)
# Build with shared libraries (.so) for Python bindings
# Note: Version mismatch warning is non-critical, liboqs-python works with newer liboqs
RUN git clone --depth 1 --branch main https://github.com/open-quantum-safe/liboqs.git /tmp/liboqs && \
    cd /tmp/liboqs && \
    mkdir build && \
    cd build && \
    cmake -GNinja \
        -DCMAKE_INSTALL_PREFIX=/usr/local \
        -DBUILD_SHARED_LIBS=ON \
        -DOQS_BUILD_ONLY_LIB=ON \
        .. && \
    ninja && \
    ninja install && \
    ldconfig && \
    rm -rf /tmp/liboqs

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 🔒 SECURITY: Hard gate - LibOQS must be importable (production invariant)
# This fails the build if liboqs-python is not available
RUN python -c "from oqs import KeyEncapsulation, Signature; print('✅ LibOQS verified - Post-Quantum Secure')" || \
    (echo "🔴 ERROR: LibOQS not importable! Build failed." && exit 1)

# Optional: Verify SPIFFE SDK if available (not blocking, but logs status)
RUN python -c "try:\n    import spiffe\n    print('✅ SPIFFE SDK available')\nexcept ImportError:\n    print('⚠️ SPIFFE SDK not available (optional)')" || true

# Copy application code
# Assuming the application is in the 'src' directory
COPY ./src /app/src

# Expose the port the app runs on
EXPOSE 8080

# Run the application
# We use uvicorn to run the FastAPI app found in src/core/app.py
CMD ["uvicorn", "src.core.app:app", "--host", "0.0.0.0", "--port", "8080"]
