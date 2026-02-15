# Security Scanning Setup Guide

## Overview

x0tta6bl4 includes comprehensive security scanning with:
- **Bandit** – Python security linter (HIGH/CRITICAL gate)
- **Safety** – Dependency vulnerability scanner
- **pip-audit** – Alternative dependency checker
- **Pre-commit hooks** – Automated local checks

---

## Quick Start

### 1. Enable Pre-commit Hooks (Local)

```bash
pip install pre-commit
pre-commit install
```

Now security checks run automatically before each commit.

### 2. Run Manual Security Check

```bash
./scripts/security-check.sh
```

This runs all three scanners locally.

### 3. Check Before PR

```bash
# Format code
make format

# Run security checks
./scripts/security-check.sh

# Run full test suite
make test

# Then commit/push
git add .
git commit -m "feat/sec: description"
git push
```

---

## CI/CD Pipeline

### On Every Pull Request:
1. **Bandit** scans `src/` for security issues
   - Fails on HIGH/CRITICAL
   - Reports LOW/MEDIUM as warnings
2. **Safety** checks dependencies
   - Warns on vulnerable packages
3. **pip-audit** provides additional coverage

### Schedule:
- **On PR**: All checks run
- **On push to main**: All checks run
- **Weekly (Monday 2 AM UTC)**: Full security-scan.yml runs

---

## Configuration Files

### `.pre-commit-config.yaml`
Defines local pre-commit hooks. Run:
```bash
pre-commit run --all-files
```

### `.github/workflows/ci.yml`
Main CI workflow. Security job runs on every PR.

### `.github/workflows/security-scan.yml`
Dedicated security scan workflow. Runs weekly + on manual dispatch.

---

## Understanding Results

### Bandit Output

**HIGH/CRITICAL** (Fail):
```
HIGH (B202): Test for use of flask debug true
    File: src/api/users.py:42
```
→ Must fix before merge

**MEDIUM/LOW** (Warnings):
```
MEDIUM (B106): Possible hardcoded password
    File: src/config.py:100
```
→ Review and suppress if intentional

To suppress a false positive:
```python
# nosec B106
password = os.getenv("DEFAULT_PASSWORD")
```

### Safety Report

Example vulnerability:
```
insecure-package 1.0.0 in /path/to/site-packages
    This package has a critical vulnerability
    ID: 12345
    Published: 2024-01-10
```

→ Update the package: `pip install --upgrade insecure-package`

### pip-audit

Similar to Safety but often catches different issues. Check both.

---

## Common Issues & Fixes

### Issue: Bandit flags hardcoded API keys

**Bad**:
```python
API_KEY = "sk_live_abc123"
```

**Good**:
```python
import os
API_KEY = os.getenv("API_KEY")
```

### Issue: Safety reports vulnerable package

**Solution**:
```bash
pip install --upgrade vulnerable-package
# OR update requirements.txt/pyproject.toml
```

### Issue: False positive security warning

**Suppress with comment**:
```python
# nosec B201 (explanation of why it's safe)
eval(untrusted_code)
```

Use sparingly and with justification.

---

## For CI/CD Admins

### Enable/Disable Security Checks

**To disable Bandit (not recommended)**:
```yaml
# In ci.yml, change:
- name: Run Bandit
  run: bandit ... || true  # Changed to not fail
```

**To add more checks**:
```yaml
- name: Run new-tool
  run: new-tool src/
```

### Set Failure Thresholds

Edit `ci.yml` security job:
```python
# Change severity threshold
high_critical = [r for r in report.get('results', []) 
                if r.get('severity') in ['HIGH', 'CRITICAL', 'MEDIUM']]
```

---

## Development Workflow

### Before Every Commit

```bash
# 1. Format code
black src/ tests/

# 2. Run security check locally
./scripts/security-check.sh

# 3. Run lint/type checking
make lint

# 4. Run tests
pytest tests/ -v

# 5. Commit if all pass
git commit -m "feat: description"
```

### Branch Strategy

- `main` – Protected, all checks must pass
- `develop` – Integration branch, all checks must pass
- `feat/*` – Feature branches, checks run but don't block

---

## Troubleshooting

### Pre-commit hooks slow down commits?

**Disable temporarily**:
```bash
git commit --no-verify
```

**But strongly encourage re-enabling**:
```bash
pre-commit install
```

### Too many false positives in Bandit?

Add `.bandit` config to project root:
```ini
[bandit]
exclude_dirs = ['/tests/', '/docs/']
skips = ['B101']  # Skip assert_used
```

### Dependencies not updating?

```bash
pip install --upgrade safety pip-audit
pre-commit autoupdate
```

---

## Resources

- [Bandit Documentation](https://bandit.readthedocs.io/)
- [Safety Documentation](https://safetycli.com/)
- [pip-audit Documentation](https://github.com/pypa/pip-audit)
- [Pre-commit Framework](https://pre-commit.com/)

---

## FAQ

**Q: Does security scanning slow down CI?**  
A: ~30-60 seconds per PR. Worth the security coverage.

**Q: Can we ignore certain warnings?**  
A: Yes, with `# nosec` comments, but document why.

**Q: What about other security tools (Snyk, SonarQube)?**  
A: Can be added later. Current setup covers OWASP top concerns.

**Q: How often should we run full audits?**  
A: Weekly minimum (scheduled), daily on main branch (automated).

---

## Next Steps (P1)

- [ ] SAST scanning (Snyk integration)
- [ ] DAST testing (automated penetration testing)
- [ ] Dependency pinning with lock files
- [ ] Security policy enforcement in contracts
- [ ] Regular penetration testing (quarterly, external)

