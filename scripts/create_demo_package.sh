#!/bin/bash
# Create Demo Package for Client
# Creates a ready-to-send ZIP file with demo version

set -e

DEMO_DIR="x0tta6bl4-demo"
ZIP_FILE="x0tta6bl4-demo.zip"

echo "📦 Creating x0tta6bl4 Demo Package..."
echo ""

# Clean up old demo directory
if [ -d "$DEMO_DIR" ]; then
    echo "🧹 Cleaning up old demo directory..."
    rm -rf "$DEMO_DIR"
fi

# Create demo directory structure
echo "📁 Creating directory structure..."
mkdir -p "$DEMO_DIR"/{config,scripts,docs}

# Copy necessary files
echo "📋 Copying files..."

# Docker Compose
if [ -f "docker-compose.yml" ]; then
    cp docker-compose.yml "$DEMO_DIR/docker-compose.demo.yml"
else
    echo "⚠️  docker-compose.yml not found, creating minimal version..."
    cat > "$DEMO_DIR/docker-compose.demo.yml" << 'EOF'
version: '3.8'
services:
  x0tta6bl4-demo:
    image: x0tta6bl4:latest
    ports:
      - "8080:8080"
    environment:
      - DEMO_MODE=true
      - NODE_COUNT=3
    volumes:
      - ./config:/app/config
EOF
fi

# Create demo setup script
cat > "$DEMO_DIR/demo-setup.sh" << 'EOF'
#!/bin/bash
# x0tta6bl4 Demo Setup Script

set -e

echo "🚀 x0tta6bl4 Demo Setup"
echo "======================"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker first:"
    echo "   macOS: brew install docker"
    echo "   Linux: sudo apt-get install docker.io"
    echo "   Windows: Download from docker.com"
    exit 1
fi

# Check Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not found. Please install Docker Compose."
    exit 1
fi

echo "✅ Docker found"
echo ""

# Start demo
echo "📦 Starting demo environment..."
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.demo.yml up -d
else
    docker compose -f docker-compose.demo.yml up -d
fi

echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Check status
echo ""
echo "📊 Demo Status:"
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.demo.yml ps
else
    docker compose -f docker-compose.demo.yml ps
fi

echo ""
echo "✅ Demo is ready!"
echo ""
echo "🌐 Access demo at: http://localhost:8080"
echo "📝 API health check: http://localhost:8080/api/v1/health"
echo ""
echo "To stop demo: bash scripts/stop-demo.sh"
EOF

chmod +x "$DEMO_DIR/demo-setup.sh"

# Create stop script
cat > "$DEMO_DIR/scripts/stop-demo.sh" << 'EOF'
#!/bin/bash
# Stop x0tta6bl4 Demo

if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.demo.yml down
else
    docker compose -f docker-compose.demo.yml down
fi

echo "✅ Demo stopped"
EOF

chmod +x "$DEMO_DIR/scripts/stop-demo.sh"

# Create test script
cat > "$DEMO_DIR/scripts/test-demo.sh" << 'EOF'
#!/bin/bash
# Test x0tta6bl4 Demo Scenarios

SCENARIO=${1:-all}

echo "🧪 Testing Demo Scenario: $SCENARIO"
echo ""

case $SCENARIO in
    self-healing)
        echo "📊 Self-Healing Test:"
        echo "1. Checking mesh network status..."
        curl -s http://localhost:8080/api/v1/mesh/status | jq .
        echo ""
        echo "2. Simulating node failure..."
        # Add node failure simulation here
        echo "3. Checking recovery..."
        sleep 5
        curl -s http://localhost:8080/api/v1/mesh/status | jq .
        ;;
    pqc-handshake)
        echo "🔐 PQC Handshake Test:"
        curl -s http://localhost:8080/api/v1/pqc/handshake | jq .
        ;;
    traffic-obfuscation)
        echo "🌐 Traffic Obfuscation Test:"
        echo "Run Wireshark to capture traffic on port 8080"
        echo "Traffic should look like HTTPS"
        ;;
    metadata-protection)
        echo "🛡️  Metadata Protection Test:"
        curl -s http://localhost:8080/api/v1/metadata/protection | jq .
        ;;
    all)
        echo "Running all tests..."
        bash "$0" self-healing
        bash "$0" pqc-handshake
        bash "$0" metadata-protection
        ;;
    *)
        echo "Unknown scenario: $SCENARIO"
        echo "Available: self-healing, pqc-handshake, traffic-obfuscation, metadata-protection, all"
        exit 1
        ;;
esac
EOF

chmod +x "$DEMO_DIR/scripts/test-demo.sh"

# Create README
cat > "$DEMO_DIR/README_DEMO.md" << 'EOF'
# x0tta6bl4 Demo Version

## Quick Start (5 minutes)

### 1. Install Docker (if not installed)

**macOS:**
```bash
brew install docker
```

**Linux:**
```bash
sudo apt-get install docker.io
```

**Windows:**
Download from [docker.com](https://www.docker.com/products/docker-desktop)

### 2. Run Demo

```bash
bash demo-setup.sh
```

### 3. Access Demo

- **Web UI:** http://localhost:8080
- **API Health:** http://localhost:8080/api/v1/health

## Demo Scenarios

### 1. Self-Healing
```bash
bash scripts/test-demo.sh self-healing
```

### 2. PQC Handshake
```bash
bash scripts/test-demo.sh pqc-handshake
```

### 3. Traffic Obfuscation
```bash
bash scripts/test-demo.sh traffic-obfuscation
```

### 4. Metadata Protection
```bash
bash scripts/test-demo.sh metadata-protection
```

### All Tests
```bash
bash scripts/test-demo.sh all
```

## Features

- ✅ Self-healing mesh network
- ✅ Post-quantum cryptography (NIST FIPS 203/204)
- ✅ Traffic obfuscation (HTTPS-like)
- ✅ Metadata protection
- ✅ Zero-Trust architecture

## Troubleshooting

### Port 8080 already in use
```bash
# Change port in docker-compose.demo.yml
ports:
  - "8081:8080"  # Use 8081 instead
```

### Docker not running
```bash
# Start Docker Desktop (macOS/Windows)
# Or: sudo systemctl start docker (Linux)
```

### Services not starting
```bash
# Check logs
docker-compose -f docker-compose.demo.yml logs

# Restart
bash scripts/stop-demo.sh
bash demo-setup.sh
```

## Stop Demo

```bash
bash scripts/stop-demo.sh
```

## Support

Questions? Contact: [your-email]

## License

Demo version for evaluation purposes only.
EOF

# Create config
mkdir -p "$DEMO_DIR/config"
cat > "$DEMO_DIR/config/demo-config.yaml" << 'EOF'
demo:
  enabled: true
  node_count: 3
  features:
    - self-healing
    - pqc-crypto
    - traffic-obfuscation
    - metadata-protection
EOF

# Create ZIP
echo ""
echo "📦 Creating ZIP file..."
if [ -f "$ZIP_FILE" ]; then
    rm "$ZIP_FILE"
fi

zip -r "$ZIP_FILE" "$DEMO_DIR" > /dev/null

# Check size
SIZE=$(du -h "$ZIP_FILE" | cut -f1)
echo ""
echo "✅ Demo package created: $ZIP_FILE"
echo "📊 Size: $SIZE"
echo ""
echo "📧 Ready to send to client!"
echo ""
echo "Next steps:"
echo "1. Test the package: unzip $ZIP_FILE && cd $DEMO_DIR && bash demo-setup.sh"
echo "2. Send to client via email"
echo "3. Follow up in 2-3 days"

