# 📦 x0tta6bl4 v3.4 - Installation & Quick Start

**Self-healing mesh network with post-quantum cryptography**

---

## 🚀 Quick Start

### Minimal Installation

```bash
# Install core dependencies
pip install -r requirements-core.txt

# Run
python3 -m src.core.app
```

### Full Installation

```bash
# Core + Optional dependencies
pip install -r requirements-core.txt
pip install -r requirements-optional.txt

# For production
export X0TTA6BL4_PRODUCTION=true
pip install -r requirements-production.txt
```

---

## 📋 Dependencies Structure

- **requirements-core.txt** - Mandatory dependencies
- **requirements-production.txt** - Required in production mode
- **requirements-optional.txt** - Optional with graceful degradation

See [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) for details.

---

## 🔍 Health Checks

```bash
# Check dependencies
python3 scripts/check_dependencies.py

# API health check
curl http://localhost:8000/health
curl http://localhost:8000/health/dependencies
```

---

## 📚 Documentation

- [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md) - Detailed installation
- [PRODUCTION_READINESS_CHECKLIST.md](PRODUCTION_READINESS_CHECKLIST.md) - Production checklist
- [REQUIRED_VS_OPTIONAL_DEPENDENCIES.md](REQUIRED_VS_OPTIONAL_DEPENDENCIES.md) - Dependencies guide
- [AUDIT_INTEGRATION_PLAN.md](AUDIT_INTEGRATION_PLAN.md) - Development roadmap

---

## ⚠️ Production Mode

In production mode (`X0TTA6BL4_PRODUCTION=true`):
- `liboqs-python` is **MANDATORY** (system won't start without it)
- `py-spiffe` is **RECOMMENDED** (system works without it but with warnings)

---

**Version:** 3.4.0  
**Status:** ✅ Technical Ready (85-90%)

