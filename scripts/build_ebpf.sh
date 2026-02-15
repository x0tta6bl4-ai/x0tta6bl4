#!/bin/bash
set -e

# Configuration
BPF_DIR="src/network/ebpf"
PROGRAMS_DIR="${BPF_DIR}/programs"
HEADERS_DIR="${BPF_DIR}/headers"
BUILD_DIR="build/ebpf-artifacts"

# Ensure LLVM/Clang is available
if command -v clang >/dev/null 2>&1; then
    CLANG="clang"
elif command -v clang-14 >/dev/null 2>&1; then
    CLANG="clang-14"
else
    echo "❌ Clang not found. Please install llvm/clang."
    exit 1
fi

LLVM_STRIP="llvm-strip"
if ! command -v $LLVM_STRIP >/dev/null 2>&1; then
    # try versioned
    if command -v llvm-strip-14 >/dev/null 2>&1; then
        LLVM_STRIP="llvm-strip-14"
    fi
fi

echo "🔧 Using ${CLANG}..."

# Create directories
mkdir -p "${BUILD_DIR}"
if [ ! -d "${HEADERS_DIR}" ]; then
    echo "⚠️  Headers directory not found at ${HEADERS_DIR}. Creating generic headers dir."
    mkdir -p "${HEADERS_DIR}"
    # Minimal headers might be needed if not using system headers
fi

# Compile Programs
echo "🔨 Compiling eBPF programs..."

for src in "${PROGRAMS_DIR}"/*.c; do
    [ -e "$src" ] || continue
    prog_name=$(basename "$src" .c)
    obj_out="${BUILD_DIR}/${prog_name}.o"

    echo "  → Compiling ${prog_name}..."
    
    # Compilation flags
    # -O2: Required for BPF
    # -target bpf: Generate BPF bytecode
    # -c: Compile only
    # -g: Debug info (BTF)
    
    $CLANG \
        -O2 \
        -g \
        -target bpf \
        -D__KERNEL__ \
        -D__BPF_TRACING__ \
        -D__TARGET_ARCH_x86 \
        -D__x86_64__ \
        -I"${HEADERS_DIR}" \
        -I"${PROGRAMS_DIR}/vmlinux" \
        -I/usr/include/$(uname -m)-linux-gnu \
        -c "${src}" \
        -o "${obj_out}"
    
    if [ $? -eq 0 ]; then
        echo "  ✅ Compiled ${obj_out}"
        # Strip if tool available (optional, reduces size)
        if command -v $LLVM_STRIP >/dev/null 2>&1; then
             $LLVM_STRIP -g "${obj_out}"
        fi
    else
        echo "  ❌ Failed to compile ${prog_name}"
        exit 1
    fi
done

echo "🎉 eBPF Build Complete!"
ls -lh "${BUILD_DIR}"
