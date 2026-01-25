# Contributing to x0tta6bl4

Thank you for your interest in contributing to x0tta6bl4! This document provides guidelines and instructions for contributing.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)
- [Security Issues](#security-issues)

---

## 🤝 Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Git
- Docker (optional, for containerized development)

### Setup

1. **Fork the repository**

2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/x0tta6bl4.git
   cd x0tta6bl4
   ```

3. **Install dependencies:**
   ```bash
   make install
   # or
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **Run tests to verify setup:**
   ```bash
   make test
   ```

---

## 🔄 Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation updates

### Creating a Branch

```bash
# Feature
git checkout -b feature/your-feature-name

# Bug fix
git checkout -b fix/issue-number-description

# Documentation
git checkout -b docs/update-readme
```

---

## 📝 Coding Standards

### Python Style

- Follow **PEP 8** style guide
- Use **type hints** for all functions
- Maximum line length: **120 characters**
- Use **black** for formatting:
  ```bash
  make format
  ```

### Code Quality

- Run **flake8** for linting:
  ```bash
  make lint
  ```

- Use **mypy** for type checking:
  ```bash
  mypy src/
  ```

### Best Practices

- ✅ Write **self-documenting code**
- ✅ Add **docstrings** (Google style)
- ✅ Keep functions **small and focused**
- ✅ Follow **SOLID principles**
- ✅ Write **tests** for new code

### Example

```python
def optimized_handshake(
    peer_id: str,
    peer_public_key: bytes,
    use_hybrid: bool = True
) -> Tuple[bytes, Dict[str, Any]]:
    """
    Perform optimized PQC handshake with caching.
    
    Args:
        peer_id: Unique identifier for the peer
        peer_public_key: Public key of the peer
        use_hybrid: Whether to use hybrid encryption
        
    Returns:
        Tuple of (shared_secret, metrics_dict)
        
    Raises:
        ValueError: If peer_id is empty
        CryptoError: If handshake fails
    """
    if not peer_id:
        raise ValueError("peer_id cannot be empty")
    
    # Implementation...
    return shared_secret, metrics
```

---

## 🧪 Testing

### Running Tests

```bash
# All tests
make test

# Specific test file
pytest tests/test_pqc_performance.py -v

# With coverage
make test-coverage
```

### Writing Tests

- ✅ Write tests for **all new features**
- ✅ Aim for **>70% coverage**
- ✅ Use **pytest** fixtures
- ✅ Test **edge cases** and **error conditions**

### Test Structure

```python
import pytest
from src.security.pqc_performance import PQCPerformanceOptimizer

class TestPQCPerformanceOptimizer:
    """Test suite for PQC Performance Optimizer."""
    
    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance."""
        return PQCPerformanceOptimizer(enable_cache=True)
    
    def test_handshake_with_cache(self, optimizer):
        """Test handshake with cache enabled."""
        # Test implementation
        pass
    
    def test_handshake_without_cache(self, optimizer):
        """Test handshake without cache."""
        # Test implementation
        pass
```

---

## 📚 Documentation

### Code Documentation

- Add **docstrings** to all public functions/classes
- Use **Google-style** docstrings
- Include **type hints**

### Documentation Updates

- Update relevant `.md` files
- Add examples if applicable
- Update API reference if needed

---

## 📤 Submitting Changes

### Pull Request Process

1. **Update your branch:**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout feature/your-feature
   git rebase develop
   ```

2. **Ensure tests pass:**
   ```bash
   make test
   make lint
   ```

3. **Commit your changes:**
   ```bash
   git add .
   git commit -m "feat: Add new feature description"
   ```

   **Commit message format:**
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation
   - `test:` - Tests
   - `refactor:` - Code refactoring
   - `perf:` - Performance improvement

4. **Push to your fork:**
   ```bash
   git push origin feature/your-feature
   ```

5. **Create Pull Request:**
   - Use the PR template
   - Describe changes clearly
   - Link related issues
   - Request review from maintainers

### PR Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No linter errors
- [ ] Type hints added
- [ ] Commit messages follow convention

---

## 🔒 Security Issues

**DO NOT** open public issues for security vulnerabilities.

Instead, email: **security@x0tta6bl4.net**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

---

## 🎯 Areas for Contribution

### High Priority

- [ ] SPIFFE/PQC Integration
- [ ] ML-DSA-65 for configurations
- [ ] RAG Pipeline Enhancement (BM25)
- [ ] Performance optimizations
- [ ] Additional test coverage

### Medium Priority

- [ ] Kubernetes operators
- [ ] Monitoring dashboards
- [ ] Documentation improvements
- [ ] Example applications
- [ ] Tutorial videos

### Low Priority

- [ ] UI improvements
- [ ] Localization
- [ ] Additional examples

---

## ❓ Questions?

- **GitHub Discussions:** For questions and discussions
- **GitHub Issues:** For bug reports and feature requests
- **Email:** contact@x0tta6bl4.net

---

## 🙏 Thank You!

Your contributions make x0tta6bl4 better for everyone. We appreciate your time and effort!

---

**Happy coding!** 🚀

