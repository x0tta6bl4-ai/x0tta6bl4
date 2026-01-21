# Makefile for x0tta6bl4 eBPF Programs
# 
# Requirements:
# - clang >= 10
# - llvm >= 10
# - linux kernel headers
# - libbpf (for CO-RE support)

CLANG ?= clang
LLC ?= llc
ARCH ?= $(shell uname -m | sed 's/x86_64/x86/' | sed 's/aarch64/arm64/')
KERNEL_VERSION ?= $(shell uname -r)

# Include directories for headers (kernel space, minimal)
INCLUDES = -I/usr/src/linux-headers-$(KERNEL_VERSION)/include/uapi \
           -I/usr/src/linux-headers-$(KERNEL_VERSION)/include

# Compiler flags with optimizations
CLANG_FLAGS = -O2 \
              -target bpf \
              -D__BPF_TRACING__ \
              -D__KERNEL__ \
              -Wall \
              -Wno-unused-value \
              -Wno-pointer-sign \
              -Wno-compare-distinct-pointer-types \
              -Wno-unknown-attributes \
              $(INCLUDES)

# Output directories
OBJ_DIR = .
VMLINUX_DIR = vmlinux

# Source files
SOURCES = xdp_counter.c \
          xdp_mesh_filter.c \
          xdp_pqc_verify.c \
          tracepoint_net.c \
          tc_classifier.c \
          kprobe_syscall_latency.c \
          kprobe_syscall_latency_secure.c

# Object files
OBJECTS = $(SOURCES:.c=.o)

.PHONY: all clean verify test install vmlinux help

all: $(OBJECTS)
	@echo "✨ All eBPF programs compiled successfully"

# Generate vmlinux.h for CO-RE if available
vmlinux:
	@if [ -f /sys/kernel/btf/vmlinux ] && command -v bpftool &> /dev/null; then \
		echo "📦 Generating vmlinux.h for CO-RE..."; \
		mkdir -p $(VMLINUX_DIR); \
		bpftool btf dump file /sys/kernel/btf/vmlinux format c > $(VMLINUX_DIR)/vmlinux.h; \
		echo "✅ vmlinux.h generated"; \
	else \
		echo "⚠️  BTF not available, skipping vmlinux.h generation"; \
	fi

%.o: %.c vmlinux
	@echo "🔨 Compiling $<..."
	@$(CLANG) $(CLANG_FLAGS) -c $< -o $(OBJ_DIR)/$@
	@echo "   ✅ Generated: $(OBJ_DIR)/$@"

clean:
	rm -f $(OBJECTS)
	rm -rf $(VMLINUX_DIR)
	@echo "🧹 Cleaned eBPF artifacts"

# Verify all compiled objects
verify: $(OBJECTS)
	@echo "🔍 Verifying eBPF programs..."
	@success=true; \
	for obj in $(OBJECTS); do \
		if file $$obj 2>/dev/null | grep -q "ELF.*BPF"; then \
			echo "  ✅ $$obj - Valid eBPF object"; \
		else \
			echo "  ❌ $$obj - INVALID (not eBPF format)"; \
			success=false; \
		fi; \
	done; \
	if [ "$$success" = "true" ]; then \
		echo "🎉 All eBPF programs verified successfully"; \
	else \
		echo "⚠️  Some eBPF programs are invalid"; \
		exit 1; \
	fi

# Test compilation (lint-like check)
test: clean all verify
	@echo "🧪 Running eBPF compilation tests..."
	@ls -lah $(OBJECTS)
	@echo "✅ All tests passed"

# Install compiled objects to build directory (for CI/CD)
install: $(OBJECTS) verify
	@echo "📦 Installing eBPF objects..."
	@mkdir -p ../../../build/ebpf
	@cp $(OBJECTS) ../../../build/ebpf/
	@echo "✅ Installation complete: ../../../build/ebpf/"

# Display help
help:
	@echo "eBPF Programs Makefile"
	@echo "======================"
	@echo "Targets:"
	@echo "  all      - Compile all eBPF programs (default)"
	@echo "  clean    - Remove compiled objects and vmlinux.h"
	@echo "  verify   - Verify all compiled objects are valid eBPF"
	@echo "  test     - Run clean build and verify"
	@echo "  install  - Install compiled objects to build/ebpf/"
	@echo "  vmlinux  - Generate vmlinux.h for CO-RE support"
	@echo "  help     - Display this help message"
	@echo ""
	@echo "Variables:"
	@echo "  CLANG    - Path to clang compiler (default: clang)"
	@echo "  ARCH     - Target architecture (auto-detected)"
	@echo "  KERNEL_VERSION - Kernel version (auto-detected)"
