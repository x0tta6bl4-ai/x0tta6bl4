# Version Contract Documentation

## Overview

The x0tta6bl4 project uses a centralized version management system to ensure consistency across all components.

## Single Source of Truth

All version information is managed in [`src/version.py`](../src/version.py):

```python
from src.version import __version__, get_version_info

# Get current version
print(__version__)  # "3.3.0"

# Get structured version info
info = get_version_info()
print(info.api_version)    # "3.3.0"
print(info.docker_tag)     # "3.3.0"
print(info.user_agent)     # "x0tta6bl4/3.3.0"
```

## Version Policy

We follow **Option B** from the execution backlog:

- **API reports project release version** (not separate API version)
- **Single version for all components**
- **Semantic Versioning**: MAJOR.MINOR.PATCH

### Version Components

| Component | Description | Example |
|-----------|-------------|---------|
| MAJOR | Breaking changes | 3 |
| MINOR | New features, backward compatible | 2 |
| PATCH | Bug fixes | 1 |
| Channel | Release stability | stable, beta, alpha |
| Build | CI/CD build number | Optional |

## Usage

### In Python Code

```python
# Import version
from src.version import __version__, get_health_info

# Use in FastAPI app
app = FastAPI(
    title="x0tta6bl4",
    version=__version__,
)

# Use in health endpoint
@app.get("/health")
async def health():
    return {"status": "ok", "version": __version__}

# Use in metrics
info = get_health_info()
# Returns: {"version": "3.3.0", "full_version": "3.3.0", "channel": "stable", ...}
```

### In Docker

```bash
# Build with version tag
docker build -t x0tta6bl4:3.3.0 .

# Or use the docker_tag helper
VERSION=$(python -c "from src.version import get_docker_tag; print(get_docker_tag())")
docker build -t x0tta6bl4:$VERSION .
```

### In CI/CD

```yaml
# GitLab CI
variables:
  VERSION: $(python -c "from src.version import __version__; print(__version__)")

build:
  script:
    - docker build -t x0tta6bl4:$VERSION .
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `X0TTA6BL4_VERSION` | Override version | From src/version.py |
| `X0TTA6BL4_BUILD` | Build metadata | Empty |
| `X0TTA6BL4_CHANNEL` | Release channel | stable |
| `GIT_COMMIT` | Git commit hash | Empty |

## Compatibility Checks

```python
from src.version import is_compatible, check_min_version

# Check if compatible with required version
if is_compatible("3.3.0"):
    print("Compatible!")

# Enforce minimum version (raises RuntimeError if not met)
check_min_version("3.3.0")
```

## Migration Guide

### Before (Hardcoded Versions)

```python
# DON'T DO THIS
_VERSION = "3.3.0"
app = FastAPI(version="3.3.0")
return {"version": "3.2.0"}  # Inconsistent!
```

### After (Centralized Version)

```python
# DO THIS
from src.version import __version__
app = FastAPI(version=__version__)
return {"version": __version__}  # Consistent!
```

## Files Updated

The following files have been updated to use the centralized version:

| File | Change |
|------|--------|
| `src/core/app.py` | Import `__version__` from `src.version` |
| `src/core/health.py` | Import `__version__` from `src.version` |
| `src/ml/__init__.py` | Import `__version__` from `src.version` |
| `src/monitoring/v3_metrics.py` | Import `__version__` from `src.version` |
| `src/api/v3_endpoints.py` | Import `__version__` from `src.version` |

## Testing

Run version tests:

```bash
pytest tests/unit/test_version.py -v
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.3.0 | 2026-02-23 | Version source unification and contract automation |
| 3.2.1 | 2026-02-20 | Version contract unification |
| 3.2.0 | 2026-02-20 | Event Store Database Backends |
| 3.1.0 | 2026-02-17 | MeshRouter refactoring |
| 3.0.0 | 2026-01-27 | Phase 1 complete |

## Related Documentation

- [STATUS.md](./STATUS.md) - Project status
- [EXECUTION_BACKLOG_Q1_2026_W7_W8.md](../plans/EXECUTION_BACKLOG_Q1_2026_W7_W8.md) - Version contract task details
