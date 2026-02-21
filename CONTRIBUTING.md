# Contributing to x0tta6bl4

Thank you for your interest in contributing to x0tta6bl4! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Security Issues](#security-issues)

---

## Code of Conduct

### Our Pledge

We as members, contributors, and leaders pledge to make participation in our community a harassment-free experience for everyone, regardless of age, body size, visible or invisible disability, ethnicity, sex characteristics, gender identity and expression, level of experience, education, socio-economic status, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior includes:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

**Unacceptable behavior includes:**
- The use of sexualized language or imagery
- Trolling, insulting/derogatory comments, and personal or political attacks
- Public or private harassment
- Publishing others' private information without explicit permission
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by contacting the project team at conduct@x0tta6bl4.net. All complaints will be reviewed and investigated and will result in a response that is deemed necessary and appropriate.

---

## How to Contribute

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

```markdown
**Description**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected Behavior**
A clear description of what you expected to happen.

**Environment**
- OS: [e.g. Ubuntu 22.04]
- Python version: [e.g. 3.12.0]
- x0tta6bl4 version: [e.g. 1.0.0]

**Additional Context**
Add any other context about the problem here.
```

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Title**: Clear, descriptive title
- **Description**: Detailed description of the proposed enhancement
- **Motivation**: Why is this enhancement useful?
- **Alternatives**: Have you considered any alternatives?
- **Additional Context**: Any other context or screenshots

### Your First Code Contribution

Unsure where to begin? Look for issues labeled:
- `good first issue` - good for newcomers
- `help wanted` - extra attention is needed
- `documentation` - documentation improvements

---

## Development Setup

### Prerequisites

- Python 3.12+
- Poetry (recommended) or pip
- Docker & Docker Compose
- pre-commit
- liboqs (for PQC testing)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/x0tta6bl4/x0tta6bl4.git
cd x0tta6bl4

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests to verify setup
pytest tests/ -v
```

### Docker Development

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Run tests in container
docker-compose exec x0tta6bl4 pytest tests/ -v

# View logs
docker-compose logs -f x0tta6bl4
```

---

## Code Style Guidelines

### Python Style

We follow PEP 8 with some modifications:

```python
# Good: Type hints are required for public functions
def process_packet(
    packet: bytes,
    source: str,
    destination: str,
) -> PacketResult:
    """Process a network packet through the mesh.
    
    Args:
        packet: Raw packet bytes
        source: Source node identifier
        destination: Destination node identifier
        
    Returns:
        PacketResult with processing status
        
    Raises:
        PacketError: If packet is malformed
    """
    # Implementation
    pass
```

### Formatting Tools

We use the following tools (configured in `.pre-commit-config.yaml`):

| Tool | Purpose |
|------|---------|
| `black` | Code formatting |
| `isort` | Import sorting |
| `ruff` | Linting |
| `mypy` | Type checking |
| `bandit` | Security linting |

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

### Docstrings

Use Google-style docstrings:

```python
def calculate_phi_ratio(metrics: Dict[str, float]) -> float:
    """Calculate the phi-ratio based on system metrics.
    
    The phi-ratio represents system harmony, approaching 1.618 (golden ratio)
    when the system is in perfect balance.
    
    Args:
        metrics: Dictionary containing system metrics:
            - cpu_percent: CPU utilization (0-100)
            - memory_percent: Memory utilization (0-100)
            - latency_ms: Network latency in milliseconds
            - packet_loss: Packet loss percentage (0-100)
            - mesh_connectivity: Number of active mesh peers
    
    Returns:
        Phi-ratio value between 0 and ~1.618
    
    Example:
        >>> metrics = {"cpu_percent": 60, "memory_percent": 65}
        >>> phi = calculate_phi_ratio(metrics)
        >>> phi > 1.0
        True
    """
    pass
```

### Import Organization

```python
# Standard library
import asyncio
import logging
from typing import Dict, List, Optional

# Third-party
import numpy as np
from fastapi import FastAPI

# Local imports
from src.core.consciousness import ConsciousnessEngine
from src.security.pqc import PQCKeyExchange
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Modules | snake_case | `mape_k_loop.py` |
| Classes | PascalCase | `ConsciousnessEngine` |
| Functions | snake_case | `calculate_phi_ratio()` |
| Constants | UPPER_SNAKE_CASE | `MTTR_TARGET = 3.14` |
| Private | _leading_underscore | `_internal_state` |

---

## Testing

### Test Structure

```
tests/
    unit/               # Unit tests
    integration/        # Integration tests
    e2e/               # End-to-end tests
    ebpf/              # eBPF tests (requires root)
    conftest.py        # Pytest fixtures
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html --cov-report=term

# Specific test file
pytest tests/unit/test_consciousness.py -v

# Specific test
pytest tests/unit/test_consciousness.py::test_calculate_phi_ratio -v

# eBPF tests (requires root)
sudo pytest tests/ebpf/ -v
```

### Test Requirements

- **Coverage**: New code requires >80% coverage
- **All tests must pass**: PRs with failing tests will not be merged
- **Mutation testing**: Critical modules should pass mutation tests

### Writing Tests

```python
import pytest
from src.core.consciousness import ConsciousnessEngine, ConsciousnessState


class TestConsciousnessEngine:
    """Tests for ConsciousnessEngine."""
    
    @pytest.fixture
    def engine(self) -> ConsciousnessEngine:
        """Create a ConsciousnessEngine instance for testing."""
        return ConsciousnessEngine(enable_advanced_metrics=False)
    
    def test_calculate_phi_ratio_euphoric(self, engine: ConsciousnessEngine):
        """Test phi-ratio calculation for euphoric state."""
        metrics = {
            "cpu_percent": 60,
            "memory_percent": 65,
            "latency_ms": 85,
            "packet_loss": 0.5,
            "mesh_connectivity": 20,
        }
        
        phi = engine.calculate_phi_ratio(metrics)
        
        assert phi > 1.4, "Euphoric state should have phi > 1.4"
    
    @pytest.mark.parametrize("state,expected_range", [
        (ConsciousnessState.EUPHORIC, (1.4, 2.0)),
        (ConsciousnessState.HARMONIC, (1.0, 1.4)),
        (ConsciousnessState.CONTEMPLATIVE, (0.8, 1.0)),
        (ConsciousnessState.MYSTICAL, (0.0, 0.8)),
    ])
    def test_state_ranges(
        self,
        engine: ConsciousnessEngine,
        state: ConsciousnessState,
        expected_range: tuple,
    ):
        """Test consciousness state evaluation."""
        # Test implementation
        pass
```

---

## Pull Request Process

### Before Submitting

1. **Create an issue** (if one doesn't exist)
2. **Fork the repository** and create your branch from `main`
3. **Make your changes** following code style guidelines
4. **Add tests** for new functionality
5. **Update documentation** if needed
6. **Run tests locally**:
   ```bash
   pytest tests/ -v
   pre-commit run --all-files
   ```

### PR Checklist

```markdown
- [ ] Code follows the project's style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)
- [ ] No new security vulnerabilities introduced
```

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
Describe testing performed

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] CHANGELOG updated
```

### Review Process

1. **Automated checks**: CI must pass (tests, linting, security)
2. **Code review**: At least 1 approval required
3. **Security review**: Required for security-related changes
4. **Merge**: Squash and merge to `main`

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring
- `security/description` - Security fixes

---

## Security Issues

**Do not open public issues for security vulnerabilities.**

Instead, please report security issues privately:

1. Email: security@x0tta6bl4.net
2. Include: Description, steps to reproduce, potential impact
3. Response time: Within 48 hours

See [SECURITY.md](SECURITY.md) for full security policy.

---

## Getting Help

- **Documentation**: [docs.x0tta6bl4.net](https://docs.x0tta6bl4.net)
- **Discord**: [discord.gg/x0tta6bl4](https://discord.gg/x0tta6bl4)
- **Email**: dev@x0tta6bl4.net

---

## License

By contributing to x0tta6bl4, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing! :heart:
