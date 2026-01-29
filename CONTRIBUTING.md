# Contributing to x0tta6bl4

Thank you for considering contributing to x0tta6bl4! We welcome contributions from the community.

## How to Contribute

### 1. Reporting Issues

If you find a bug or have a feature request:

1. Check if the issue already exists in the [GitHub Issues](https://github.com/x0tta6bl4-ai/x0tta6bl4/issues)
2. If not, create a new issue with:
   - Clear, descriptive title
   - Detailed description of the problem or feature
   - Steps to reproduce (for bugs)
   - Expected behavior
   - Environment information

### 2. Making Changes

To contribute code changes:

1. Fork the repository
2. Create a new branch from `main`
3. Make your changes
4. Add tests for your changes
5. Run the test suite
6. Commit your changes with meaningful commit messages
7. Push your branch to your forked repository
8. Create a pull request

### 3. Pull Request Guidelines

- Keep PRs small and focused on a single feature or fix
- Include clear description of what the PR does
- Reference any related issues
- Ensure all tests pass
- Follow the coding style guidelines

## Getting Started

### Prerequisites

- Python 3.10+
- Docker & Docker Compose
- Kubernetes 1.20+ (recommended)
- PostgreSQL 13+
- Redis 6+ (optional)

### Local Development

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
docker-compose up
```

### Running Tests

```bash
pytest tests/unit/ -v --tb=short
```

### Building the Project

```bash
docker build -t x0tta6bl4:latest -f Dockerfile.app .
```

## Coding Style Guidelines

### Python

- Follow PEP 8 guidelines
- Use type hints for all function signatures
- Write clear docstrings for all classes and functions
- Keep lines under 80 characters where possible

### Commit Messages

Use semantic commit messages:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes
- `refactor:` Code refactoring
- `test:` Test additions
- `chore:` Maintenance tasks

Example:
```
feat: Add support for ML-KEM-768 key exchange
```

## Code of Conduct

Please follow our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions.

## License

By contributing to x0tta6bl4, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
