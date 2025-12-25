# Makefile for x0tta6bl4 eBPF Programs
# 
# Requirements:
# - clang >= 10
# - llvm >= 10
# - linux kernel headers
# - libbpf (for CO-RE)

CLANG ?= clang
LLC ?= llc
ARCH ?= $(shell uname -m | sed 's/x86_64/x86/' | sed 's/aarch64/arm64/')
KERNEL_VERSION ?= $(shell uname -r)

# Include directories
INCLUDES = -I/usr/include \
           -I/usr/include/$(ARCH)-linux-gnu \
           -I/usr/src/linux-headers-$(KERNEL_VERSION)/include \
           -I/usr/src/linux-headers-$(KERNEL_VERSION)/arch/$(ARCH)/include

# Compiler flags
CLANG_FLAGS = -O2 -g \
              -target bpf \
              -D__BPF_TRACING__ \
              -Wall \
              -Wno-unused-value \
              -Wno-pointer-sign \
              -Wno-compare-distinct-pointer-types \
              -Werror \
              $(INCLUDES)

# Output directory
OBJ_DIR = .

# Source files
SOURCES = xdp_counter.c

# Object files
OBJECTS = $(SOURCES:.c=.o)

.PHONY: all clean

all: $(OBJECTS)

%.o: %.c
	@echo "Compiling $<..."
	$(CLANG) $(CLANG_FLAGS) -c $< -o $(OBJ_DIR)/$@
	@echo "✅ Compiled: $(OBJ_DIR)/$@"

clean:
	rm -f $(OBJECTS)
	@echo "🧹 Cleaned eBPF object files"

# Verify compilation
verify: $(OBJECTS)
	@echo "🔍 Verifying eBPF programs..."
	@for obj in $(OBJECTS); do \
		echo "  Checking $$obj..."; \
		file $$obj | grep -q "ELF.*eBPF" && echo "    ✅ Valid eBPF object" || echo "    ❌ Invalid"; \
	done

