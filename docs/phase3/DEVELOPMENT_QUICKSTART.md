# Phase 3 Development Quick Start

## ⚡ Quick Start (5 minutes)

### 1. Install Dependencies
```bash
pip install -e ".[ml,dev,monitoring]"
```

### 2. Run Tests
```bash
# All component tests
pytest tests/test_mape_k.py -v

# Integration tests
pytest tests/test_phase3_integration.py -v

# With coverage
pytest tests/ --cov=src --cov-report=html
```

### 3. Start MAPE-K Locally
```bash
# Terminal 1: Prometheus (pre-configured)
docker run -d -p 9090:9090 \
  -v $(pwd)/config/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus

# Terminal 2: AlertManager (pre-configured)
docker run -d -p 9093:9093 \
  -v $(pwd)/config/alertmanager.yml:/etc/alertmanager/alertmanager.yml \
  prom/alertmanager

# Terminal 3: MAPE-K API
python -m src.core.app --reload

# Terminal 4: Monitor component (in Python)
python -c "
from src.mape_k.monitor import Monitor
import asyncio
m = Monitor()
asyncio.run(m.start())
"
```

### 4. Access Services
- **MAPE-K API**: http://localhost:8001
- **Prometheus**: http://localhost:9090
- **AlertManager**: http://localhost:9093

## 📚 Documentation

### Integration Architecture
```
Prometheus (9090) 
    ↓
Monitor → Analyze → Plan → Execute (Charter) → Knowledge
    ↑                                              ↓
    └──────────────────────────────────────────────┘
```

### Component Locations
- `src/mape_k/monitor.py` - Real-time violation detection
- `src/mape_k/analyze.py` - Pattern detection (4 algorithms)
- `src/mape_k/plan.py` - Policy generation
- `src/mape_k/execute.py` - Policy execution with rollback
- `src/mape_k/knowledge.py` - Learning system
- `src/mape_k/orchestrator.py` - MAPE-K coordination
- `src/integration/charter_client.py` - Charter API (real + mock)
- `src/integration/alertmanager_client.py` - AlertManager webhook handler

### Test Locations
- `tests/test_mape_k.py` - Component unit tests (60+ tests)
- `tests/test_phase3_integration.py` - Integration tests (30+ tests)

## 🔧 Development Tasks

### Add New Pattern Detection Algorithm

1. Edit `src/mape_k/analyze.py`:
```python
class PatternAnalyzer:
    def _analyze_new_pattern(self, violations):
        """New algorithm"""
        patterns = []
        for violation in violations:
            # Detection logic
            pattern = ViolationPattern(
                pattern_type="new_pattern",
                violations=[violation],
                confidence=0.8
            )
            patterns.append(pattern)
        return patterns
    
    def analyze(self, violations, metrics):
        # Add to analysis
        new_patterns = self._analyze_new_pattern(violations)
        # ... rest of analysis
```

2. Add tests in `tests/test_mape_k.py`:
```python
def test_new_pattern_detection():
    analyzer = PatternAnalyzer()
    violations = [...]
    analysis = analyzer.analyze(violations, [])
    
    patterns = [p for p in analysis.patterns if p.pattern_type == "new_pattern"]
    assert len(patterns) > 0
```

3. Run tests:
```bash
pytest tests/test_mape_k.py::TestPatternAnalyzer -v
```

### Add New Remediation Action

1. Edit `src/mape_k/plan.py`:
```python
class ActionType(str, Enum):
    NEW_ACTION = "new_action"  # Add this

class Planner:
    def _calculate_cost(self, action_type):
        costs = {
            # ... existing costs
            ActionType.NEW_ACTION: 0.25,  # Add this
        }
        return costs.get(action_type, 0.5)
```

2. Add to Execute implementation
3. Add tests
4. Document in MAPE_K_ARCHITECTURE.md

### Connect Real Charter API

1. Update Charter URL in config:
```yaml
execute:
  charter_url: http://real-charter-endpoint:8000
  use_mock: false
```

2. Configure API key:
```bash
export CHARTER_API_KEY=your-key-here
```

3. Test connection:
```python
from src.integration.charter_client import RealCharterClient
import asyncio

async def test():
    client = RealCharterClient(base_url="http://charter:8000")
    await client.connect()
    state = await client.get_committee_state()
    print(state)
    await client.disconnect()

asyncio.run(test())
```

### Run Staging Deployment

1. Build images:
```bash
docker-compose -f docker-compose.staging.yml build
```

2. Start services:
```bash
docker-compose -f docker-compose.staging.yml up -d
```

3. Check health:
```bash
# All services should be green
docker-compose -f docker-compose.staging.yml ps

# Test endpoints
curl http://localhost:8001/health       # MAPE-K
curl http://localhost:8000/health       # Charter
curl http://localhost:9090/-/healthy    # Prometheus
curl http://localhost:9093/-/healthy    # AlertManager
```

4. View logs:
```bash
docker-compose -f docker-compose.staging.yml logs -f mape-k
```

5. Stop services:
```bash
docker-compose -f docker-compose.staging.yml down
```

## 🐛 Debugging

### Enable Debug Logging
```bash
export LOG_LEVEL=DEBUG
python -m src.core.app
```

### Check Monitor Violations
```python
from src.mape_k.monitor import Monitor
import asyncio

async def debug():
    monitor = Monitor()
    violations = await monitor.get_violations()
    for v in violations:
        print(f"{v.label}: {v.value} ({v.severity})")

asyncio.run(debug())
```

### Check Analysis Results
```python
from src.mape_k.analyze import PatternAnalyzer
from src.mape_k.monitor import Violation

analyzer = PatternAnalyzer()
violations = [
    Violation(label="test", value=1.5, severity="warning", timestamp=...)
]
analysis = analyzer.analyze(violations, [])
print(f"Patterns: {analysis.patterns}")
print(f"Confidence: {[p.confidence for p in analysis.patterns]}")
```

### Check Plan Results
```python
from src.mape_k.plan import Planner
from src.mape_k.analyze import AnalysisResult

planner = Planner()
analysis = AnalysisResult(...)  # From analyzer
policies = planner.generate_policies(analysis)
for policy in policies:
    print(f"Policy {policy.id}: {len(policy.actions)} actions, score={policy.cost_benefit_score}")
```

### Mock Charter for Testing
```python
from src.integration.charter_client import get_charter_client

# Use mock for development
charter = get_charter_client(use_mock=True)
await charter.connect()
policies = await charter.get_policies()
print(f"Mock policies: {policies}")
```

## 📊 Code Quality

### Run Linter
```bash
make lint
# or
flake8 src/ tests/
```

### Run Type Checker
```bash
mypy src/
```

### Format Code
```bash
make format
# or
black src/ tests/
```

### Check Coverage
```bash
pytest tests/ --cov=src --cov-report=term-missing
# Coverage must be ≥75%
```

## 🚀 Performance

### Run Benchmarks
```bash
make benchmark
```

### Profile Components
```bash
python -m cProfile -s cumulative -c "
from src.mape_k.orchestrator import MAFEKOrchestrator
import asyncio

orch = MAFEKOrchestrator()
asyncio.run(orch.start())
" | head -20
```

## 📋 Checklist: Adding New Feature

- [ ] Create feature branch: `git checkout -b feat/my-feature`
- [ ] Write tests first (TDD)
- [ ] Implement feature
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Coverage ≥75%: `pytest --cov=src --cov-report=term-missing`
- [ ] Linting passes: `make lint`
- [ ] Type checking passes: `mypy src/`
- [ ] Code formatted: `make format`
- [ ] Documentation updated
- [ ] Integration tests pass: `pytest tests/test_phase3_integration.py -v`
- [ ] Commit: `git commit -m "feat(scope): description"`
- [ ] Push: `git push origin feat/my-feature`
- [ ] Create PR (max 400 lines diff)

## 🔗 Important Links

- **Architecture**: [MAPE-K Architecture](../phase3/MAPE_K_ARCHITECTURE.md)
- **Integration**: [Phase 3 Integration Guide](./PHASE_3_INTEGRATION_GUIDE.md)
- **API Reference**: [API Documentation](../API_REFERENCE.md)
- **Contributing**: [CONTRIBUTING.md](../../CONTRIBUTING.md)
- **Makefile**: `make help` to see all available tasks

## 🆘 Common Issues

### Issue: Tests failing with "module not found"
**Solution**: Run `pip install -e ".[ml,dev,monitoring]"` to install in dev mode

### Issue: Prometheus not responding
**Solution**: Check if running on port 9090, verify config: `curl http://localhost:9090/api/v1/status/config`

### Issue: Charter API connection refused
**Solution**: Ensure Charter is running or use mock mode: `get_charter_client(use_mock=True)`

### Issue: AlertManager webhook not receiving alerts
**Solution**: Check webhook configuration in AlertManager config, verify port 5000 is open

### Issue: Coverage below 75%
**Solution**: Add unit tests for uncovered code paths, run: `pytest --cov-report=html` to generate detailed report

## 💡 Tips

- Use `make` for common tasks: `make test`, `make lint`, `make format`, `make benchmark`
- Use pytest markers: `pytest -m unit`, `pytest -m integration`
- Use verbose mode: `pytest -vv` for detailed output
- Use pdb for debugging: `import pdb; pdb.set_trace()` in code, run: `pytest --pdb`
- Check logs: `tail -f logs/mape_k.log`
- Monitor metrics live: `watch -n 1 'curl -s http://localhost:9090/api/v1/query?query=up | jq'`

---

**Happy coding! 🚀**

For more details, see [PHASE_3_INTEGRATION_GUIDE.md](./PHASE_3_INTEGRATION_GUIDE.md)
