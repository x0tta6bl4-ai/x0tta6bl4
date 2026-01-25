🚀 x0tta6bl4 CI/CD PIPELINE - ПОЛНАЯ ДОКУМЕНТАЦИЯ

════════════════════════════════════════════════════════════════════════════

АРХИТЕКТУРА CI/CD
════════════════════════════════════════════════════════════════════════════

                    ┌─────────────────┐
                    │  git push       │
                    │  commit/PR      │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌────────┐          ┌────────┐         ┌────────┐
    │ Tests  │          │ Linting │        │ Build  │
    │ (test) │          │ (test)  │        │(docker)│
    └────┬───┘          └────┬───┘         └────┬───┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Merge to main  │
                    │  (if approved)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ git tag vX.Y.Z  │
                    │ (manual)        │
                    └────────┬────────┘
                             │
                    ┌────────▼────────────────┐
                    │ Release Workflow        │
                    │ • Verify tests pass     │
                    │ • Build packages       │
                    │ • Publish to PyPI      │
                    │ • Push Docker images   │
                    │ • Create GitHub Release│
                    └────────────────────────┘


WORKFLOWS
════════════════════════════════════════════════════════════════════════════

1. test.yml - TESTING & CODE QUALITY
   ─────────────────────────────────────
   ✅ Trigger: push to main/develop, PR to main
   ✅ Runs on: Python 3.10, 3.11, 3.12
   
   Steps:
   • Checkout code
   • Set up Python
   • Install dependencies
   • Lint (flake8)
   • Type check (mypy)
   • Format check (black)
   • Run tests (pytest 67/67)
   • Upload coverage
   • Generate test report
   
   Artifacts:
   • junit.xml (test results)
   • coverage.xml (code coverage)


2. docker.yml - BUILD & PUSH DOCKER
   ────────────────────────────────────
   ✅ Trigger: push to main/develop, tags, PRs
   ✅ Registries: GHCR (GitHub Container Registry)
   
   Steps:
   • Checkout code
   • Set up Docker Buildx
   • Log in to registry
   • Extract metadata (tags, version)
   • Build & push development image
   • Build & push production image
   
   Artifacts:
   • ghcr.io/x0tta6bl4/x0tta6bl4:latest
   • ghcr.io/x0tta6bl4/x0tta6bl4:v3.2.0
   • ghcr.io/x0tta6bl4/x0tta6bl4:prod-v3.2.0


3. release.yml - AUTOMATED RELEASES
   ──────────────────────────────────
   ✅ Trigger: git tag v*.*.*
   ✅ Publishes to: PyPI, GitHub Releases
   
   Jobs:
   
   verify:
   • Extract version from tag
   • Verify version matches pyproject.toml
   • Run tests (fail if any fail)
   
   release:
   • Generate changelog from commits
   • Parse conventional commits
   • Create categorized release notes
   • Create GitHub Release
   
   build-pypi:
   • Build distribution packages
   • Verify with twine
   • Publish to PyPI


════════════════════════════════════════════════════════════════════════════

WORKFLOW TRIGGER POINTS
════════════════════════════════════════════════════════════════════════════

Push to develop:
  ✅ test.yml: Run tests on Python 3.10-3.12
  ✅ docker.yml: Build image (tag: develop)

Pull Request to main:
  ✅ test.yml: Run tests
  ✅ docker.yml: Build image for testing

Merge to main:
  ✅ test.yml: Run final tests
  ✅ docker.yml: Build & push (tag: latest)

Git tag v3.2.0:
  ✅ release.yml: Full release workflow
     • Verify tests pass
     • Generate release notes
     • Publish to PyPI
     • Push Docker image
     • Create GitHub Release


════════════════════════════════════════════════════════════════════════════

DEVELOPMENT WORKFLOW
════════════════════════════════════════════════════════════════════════════

1. CREATE FEATURE BRANCH
   ─────────────────────
   $ git checkout -b feat/new-feature
   
   Branch naming:
   • feat/...        - New features
   • fix/...         - Bug fixes
   • perf/...        - Performance
   • sec/...         - Security
   • docs/...        - Documentation
   • test/...        - Tests

2. COMMIT WITH CONVENTIONAL COMMITS
   ───────────────────────────────
   $ git add .
   $ git commit -m "feat: add new feature"
   
   Examples:
   • feat: add ML-based anomaly detection
   • fix: resolve deadlock in executor
   • perf: optimize analyzer by 30%
   • test: add integration tests


3. PUSH AND CREATE PR
   ──────────────────
   $ git push origin feat/new-feature
   $ gh pr create --base develop
   
   CI/CD automatically:
   ✅ Runs tests on 3 Python versions
   ✅ Lints code (flake8, mypy, black)
   ✅ Builds Docker image
   ✅ Uploads coverage

4. ADDRESS REVIEW COMMENTS
   ────────────────────────
   $ git add .
   $ git commit -m "fix: address review comments"
   $ git push origin feat/new-feature
   
   CI/CD re-runs automatically

5. MERGE TO DEVELOP
   ────────────────
   After approval, GitHub merges PR to develop
   
   CI/CD automatically:
   ✅ Final tests on all Python versions
   ✅ Builds & pushes Docker (tag: develop)

6. RELEASE PREPARATION
   ───────────────────
   Maintainers merge develop → main
   
   $ git checkout main
   $ git merge develop
   $ git push origin main

7. CREATE RELEASE TAG
   ──────────────────
   Use bumpversion or manual:
   
   $ bump2version minor
   $ git push origin main --tags
   
   OR manually:
   $ git tag -a v3.3.0 -m "Release 3.3.0"
   $ git push origin v3.3.0
   
   This triggers release.yml workflow!


════════════════════════════════════════════════════════════════════════════

SEMANTIC VERSIONING
════════════════════════════════════════════════════════════════════════════

Format: MAJOR.MINOR.PATCH

3.2.0
│ │ │
│ │ └── PATCH: Bug fixes (3.2.0 → 3.2.1)
│ └──── MINOR: New features (3.2.0 → 3.3.0)
└────── MAJOR: Breaking changes (3.2.0 → 4.0.0)

Using bumpversion:

$ bump2version patch    # 3.2.0 → 3.2.1
$ bump2version minor    # 3.2.0 → 3.3.0
$ bump2version major    # 3.2.0 → 4.0.0

This automatically:
• Updates pyproject.toml
• Updates src/mape_k/__init__.py
• Commits changes
• Creates git tag


════════════════════════════════════════════════════════════════════════════

RELEASE CHECKLIST
════════════════════════════════════════════════════════════════════════════

Before creating release tag:

Code:
  ☑️ All tests pass (67/67)
  ☑️ No linting errors (black, flake8, mypy)
  ☑️ Code coverage ≥75%
  ☑️ No merge conflicts

Documentation:
  ☑️ CHANGELOG.md updated
  ☑️ API docs updated (if needed)
  ☑️ README updated (if needed)

Testing:
  ☑️ Unit tests pass
  ☑️ Integration tests pass (if applicable)
  ☑️ Manual smoke test
  ☑️ Performance baseline unchanged

Release:
  ☑️ Version in pyproject.toml correct
  ☑️ Version in __init__.py correct
  ☑️ All commits follow conventional format
  ☑️ Release notes ready

Then:
$ git tag v3.2.0
$ git push origin main --tags

CI/CD handles the rest!


════════════════════════════════════════════════════════════════════════════

GITHUB SECRETS (Required)
════════════════════════════════════════════════════════════════════════════

Configure in GitHub:
Settings → Secrets and variables → Actions

Required secrets:

PYPI_API_TOKEN
  • For publishing to PyPI
  • Create at: https://pypi.org/manage/account/tokens/
  • Format: pypi-XXXX...

CODECOV_TOKEN
  • For uploading coverage
  • Create at: https://codecov.io/
  • (Optional if using public repo)

GITHUB_TOKEN
  • Automatically provided by GitHub
  • Used for GitHub Release creation

Docker registry:
  • GHCR uses GITHUB_TOKEN automatically
  • No additional setup needed


════════════════════════════════════════════════════════════════════════════

MONITORING CI/CD
════════════════════════════════════════════════════════════════════════════

View workflow runs:
$ gh run list
$ gh run view <run-id>

View specific workflow:
$ gh run list -w test.yml
$ gh run view -w docker.yml

Logs:
$ gh run view <run-id> --log

Web interface:
• GitHub repo → Actions tab
• See all workflows and runs
• Detailed logs for each step


════════════════════════════════════════════════════════════════════════════

TROUBLESHOOTING
════════════════════════════════════════════════════════════════════════════

Tests failing in CI but passing locally:
  • Different Python version?
  • Missing dependencies?
  • Environment variables?
  • Run: pytest --verbose

Docker build failing:
  • Missing requirements?
  • Dockerfile issues?
  • Cache problems?
  • Run: docker build -t test .

PyPI publish failing:
  • Token expired?
  • Version already exists?
  • Package name conflict?
  • Check: twine check dist/*

Release not triggering:
  • Tag name correct? (v3.2.0)
  • Tag pushed? (git push --tags)
  • Workflows file valid?
  • Check Actions tab for errors


════════════════════════════════════════════════════════════════════════════

EXAMPLES
════════════════════════════════════════════════════════════════════════════

Create and release a fix:

$ git checkout -b fix/analyzer-bug
$ # Make changes
$ pytest tests/ -v  # ✓ Pass
$ git add .
$ git commit -m "fix: prevent NaN in analyzer calculations"
$ git push origin fix/analyzer-bug

✅ CI/CD runs tests, builds Docker
✅ Create PR, get approval
✅ Merge to develop
✅ Merge develop → main

$ bump2version patch  # 3.2.0 → 3.2.1
$ git push origin main --tags

✅ CI/CD automatically:
  • Runs final tests (pass: 67/67 ✓)
  • Generates release notes
  • Publishes to PyPI
  • Pushes Docker image
  • Creates GitHub Release

$ pip install --upgrade x0tta6bl4
✅ v3.2.1 installed!


════════════════════════════════════════════════════════════════════════════

NEXT STEPS
════════════════════════════════════════════════════════════════════════════

1. Configure GitHub secrets:
   • PYPI_API_TOKEN
   • CODECOV_TOKEN (optional)

2. Test the workflow:
   $ git commit --allow-empty -m "test: trigger ci"
   $ git push origin develop
   ✅ Watch Actions tab

3. Create first release:
   $ git checkout main
   $ git merge develop
   $ bump2version minor
   $ git push origin main --tags
   ✅ Release should automate!

4. Verify:
   $ pip install x0tta6bl4
   $ python -c "import x0tta6bl4; print(x0tta6bl4.__version__)"
   3.2.0

════════════════════════════════════════════════════════════════════════════
