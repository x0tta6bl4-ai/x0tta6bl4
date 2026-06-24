# x0tta6bl4 eBPF Build System
CLANG ?= clang
CFLAGS := -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu

SOURCE := qos_enforcer.c
OBJECT := qos_enforcer.o

.PHONY: all clean generate

all: $(OBJECT)

$(OBJECT): $(SOURCE)
	$(CLANG) $(CFLAGS) -c $< -o $@

# Генерация Go-скелета через bpf2go (требует установленного пакета)
generate:
	go generate ./...

clean:
	rm -f $(OBJECT)
	rm -f qos_x86_bpfel.go qos_x86_bpfel.o
