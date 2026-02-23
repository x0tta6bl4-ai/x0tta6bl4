#!/bin/bash
# x0tta6bl4 ULTIMATE Multi-Platform Build Script

mkdir -p build

echo ">>> Building x0tta6bl4 Agent for ALL targets..."

# Desktop
echo "Building Windows/Linux/macOS (x64)..."
GOOS=windows GOARCH=amd64 go build -o build/x0t-agent-win-x64.exe src/agent/main.go
GOOS=linux GOARCH=amd64 go build -o build/x0t-agent-linux-x64 src/agent/main.go
GOOS=darwin GOARCH=amd64 go build -o build/x0t-agent-macos-intel src/agent/main.go
GOOS=darwin GOARCH=arm64 go build -o build/x0t-agent-macos-m1 src/agent/main.go

# Single Board Computers (Raspberry Pi, etc)
echo "Building ARM (Raspberry Pi/IoT)..."
GOOS=linux GOARCH=arm GOARM=7 go build -o build/x0t-agent-linux-armv7 src/agent/main.go
GOOS=linux GOARCH=arm64 go build -o build/x0t-agent-linux-arm64 src/agent/main.go

# Alternative OS
echo "Building FreeBSD..."
GOOS=freebsd GOARCH=amd64 go build -o build/x0t-agent-freebsd-x64 src/agent/main.go

echo ">>> Build complete. Distribution ready."
ls -lh build/
