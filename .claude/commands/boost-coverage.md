Systematically improve test coverage for x0tta6bl4 modules.

Read the skill file at `skills/test-coverage-boost/SKILL.md` and follow the iterative process.

First, run the coverage gaps analyzer:
```bash
python3 skills/test-coverage-boost/scripts/coverage_gaps.py
```

Then measure current coverage:
```bash
python3 -m pytest tests/ --cov=src --cov-report=term-missing --tb=short -q
```

Target module (optional): $ARGUMENTS
