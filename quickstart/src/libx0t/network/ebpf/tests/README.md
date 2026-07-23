# eBPF Telemetry Module - Test Suite

Comprehensive test suite for eBPF telemetry module with unit tests, integration tests, and mock-based kernel interaction simulation.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Pytest configuration and fixtures
├── test_security_manager.py   # SecurityManager unit tests
├── test_map_reader.py        # MapReader unit tests
├── test_perf_buffer_reader.py # PerfBufferReader unit tests
├── test_prometheus_exporter.py # PrometheusExporter unit tests
├── test_integration.py        # Integration tests
└── README.md                # This file
```

## Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Install module dependencies
pip install bcc prometheus-client
```

### Run All Tests

```bash
# Run all tests
pytest src/network/ebpf/tests/

# Run with coverage
pytest src/network/ebpf/tests/ --cov=src/network/ebpf/telemetry_module --cov-report=html

# Run with verbose output
pytest src/network/ebpf/tests/ -v
```

### Run Specific Test Files

```bash
# Run SecurityManager tests
pytest src/network/ebpf/tests/test_security_manager.py -v

# Run MapReader tests
pytest src/network/ebpf/tests/test_map_reader.py -v

# Run PerfBufferReader tests
pytest src/network/ebpf/tests/test_perf_buffer_reader.py -v

# Run PrometheusExporter tests
pytest src/network/ebpf/tests/test_prometheus_exporter.py -v

# Run integration tests
pytest src/network/ebpf/tests/test_integration.py -v
```

### Run by Markers

```bash
# Run only unit tests
pytest src/network/ebpf/tests/ -m unit -v

# Run only integration tests
pytest src/network/ebpf/tests/ -m integration -v

# Skip slow tests
pytest src/network/ebpf/tests/ -m "not slow" -v

# Run tests that require root
pytest src/network/ebpf/tests/ -m requires_root -v
```

### Run Specific Tests

```bash
# Run specific test class
pytest src/network/ebpf/tests/test_security_manager.py::TestSecurityManagerInitialization -v

# Run specific test method
pytest src/network/ebpf/tests/test_security_manager.py::TestSecurityManagerInitialization::test_initialization_with_default_config -v

# Run tests matching pattern
pytest src/network/ebpf/tests/ -k "test_valid" -v
```

## Test Coverage

### SecurityManager Tests

- ✅ Initialization with default and custom config
- ✅ Metric name validation (valid, invalid, edge cases)
- ✅ Metric value validation (int, float, NaN, Inf, range)
- ✅ String sanitization (null bytes, path traversal, sensitive paths)
- ✅ Path sanitization (traversal, absolute paths)
- ✅ Event validation (all fields, invalid fields)
- ✅ Security statistics tracking

### MapReader Tests

- ✅ Initialization with config
- ✅ BCC backend reading (success, failure, edge cases)
- ✅ bpftool backend reading (success, timeout, error)
- ✅ Caching (hit, miss, expiration, clear)
- ✅ Parallel map reading (multiple maps, errors)
- ✅ Main read method (BCC first, fallback, all fail)
- ✅ Error handling (exceptions, logging)
- ✅ Performance (cache vs no cache, parallel vs sequential)
- ✅ Edge cases (None, empty, special chars, unicode)

### PerfBufferReader Tests

- ✅ Initialization with config
- ✅ Event handler registration (single, multiple, different types)
- ✅ Event processing (success, multiple handlers, no handler, exceptions)
- ✅ Queue management (add, max size, events dropped)
- ✅ Statistics tracking (initial, received, processed)
- ✅ Error handling (invalid data, malformed events)
- ✅ Lifecycle (start, stop)
- ✅ Edge cases (empty queue, all fields)

### PrometheusExporter Tests

- ✅ Initialization with config
- ✅ Metric registration (counter, gauge, histogram, summary, labels, duplicate)
- ✅ Metric setting (value, labels, not registered, invalid)
- ✅ Counter operations (increment, amount, labels)
- ✅ Batch export (single, multiple, auto-register, validation)
- ✅ HTTP server (start, already started, unavailable)
- ✅ Error handling (not found, exceptions)
- ✅ Edge cases (empty, None, zero, negative)

### Integration Tests

- ✅ Full workflow (registration, collection, export)
- ✅ Multiple programs workflow
- ✅ Custom metrics workflow
- ✅ Component interaction (MapReader→Prometheus, PerfBuffer→Prometheus, Security→MapReader)
- ✅ Error recovery (BCC unavailable, map read failure, export failure)
- ✅ Performance under load (high throughput, parallel reading, event processing)
- ✅ Lifecycle (start/stop, context manager)
- ✅ Statistics (collection, security, perf reader)
- ✅ Edge cases (empty programs, no maps, duplicate registration, large dataset)
- ✅ Real-world scenarios (performance, network, security, combined)

## Mock Objects

The test suite includes comprehensive mock objects for simulating kernel interaction without root privileges:

### MockBCC
Simulates BCC Python bindings for testing without actual eBPF programs.

### MockBpftool
Simulates bpftool CLI for testing fallback backend.

### MockPerfBuffer
Simulates perf buffer for testing event processing.

### Mock Subprocess
Simulates subprocess calls for testing bpftool interaction.

## Test Fixtures

### telemetry_config
Provides a default telemetry configuration for testing.

### mock_bpf_program
Provides a mock BPF program for testing.

### mock_bpf_program_with_maps
Provides a mock BPF program with multiple maps.

### mock_prometheus_registry
Provides a mock Prometheus registry for testing.

### mock_subprocess
Provides a mock subprocess module for testing.

### mock_time
Provides a mock time module for testing.

### mock_threading
Provides a mock threading module for testing.

### sample_metrics
Provides sample metrics for testing.

### sample_events
Provides sample events for testing.

## Test Scenarios

### Normal Operation
All components working correctly.

### BCC Unavailable
BCC not available, fallback to bpftool.

### bpftool Unavailable
Both BCC and bpftool unavailable.

### High Load
Many events and metrics being processed.

### Invalid Data
Invalid metric data being processed.

### Security Event
High severity security event being processed.

## Continuous Integration

### GitHub Actions

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov pytest-mock
          pip install bcc prometheus-client
      - name: Run tests
        run: |
          pytest src/network/ebpf/tests/ --cov=src/network/ebpf/telemetry_module --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

### GitLab CI

```yaml
test:
  image: python:3.10
  script:
    - pip install pytest pytest-cov pytest-mock
    - pip install bcc prometheus-client
    - pytest src/network/ebpf/tests/ --cov=src/network/ebpf/telemetry_module --cov-report=html
  coverage: '/coverage'
  artifacts:
    reports:
      coverage_report:
        path: coverage/
```

## Troubleshooting

### Import Errors

```bash
# If you get import errors, ensure the module is in the path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or run from the project root
cd /path/to/x0tta6bl4
pytest src/network/ebpf/tests/
```

### BCC Not Available

```bash
# Tests are designed to work without BCC
# Mock objects simulate BCC functionality
# No need to install BCC for running tests
```

### Permission Errors

```bash
# Tests use mocks and don't require root
# No special permissions needed
# Run as regular user
```

### Port Already in Use

```bash
# If port 19090 is in use, change it in conftest.py
# Or kill the process using the port
lsof -ti:19090 | xargs kill -9
```

## Best Practices

### Writing Tests

1. **Use descriptive test names**
   ```python
   def test_metric_name_validation_with_valid_input(self):
       pass
   ```

2. **Follow AAA pattern (Arrange, Act, Assert)**
   ```python
   def test_metric_validation(self):
       # Arrange
       metric_name = "valid_metric"
       
       # Act
       is_valid, error = security.validate_metric_name(metric_name)
       
       # Assert
       assert is_valid
   ```

3. **Use fixtures for common setup**
   ```python
   @pytest.fixture
   def security_manager(self, telemetry_config):
       return SecurityManager(telemetry_config)
   ```

4. **Test both success and failure cases**
   ```python
   def test_valid_input(self):
       assert validate("valid") == True
   
   def test_invalid_input(self):
       assert validate("invalid") == False
   ```

5. **Use markers for test categorization**
   ```python
   @pytest.mark.unit
   def test_unit_test(self):
       pass
   
   @pytest.mark.integration
   def test_integration_test(self):
       pass
   ```

### Running Tests

1. **Run tests before committing**
   ```bash
   pytest src/network/ebpf/tests/ -v
   ```

2. **Check coverage**
   ```bash
   pytest src/network/ebpf/tests/ --cov=src/network/ebpf/telemetry_module
   ```

3. **Run specific test during development**
   ```bash
   pytest src/network/ebpf/tests/test_security_manager.py::TestSecurityManagerInitialization::test_initialization_with_default_config -v
   ```

4. **Use verbose mode for debugging**
   ```bash
   pytest src/network/ebpf/tests/ -vv
   ```

## Test Statistics

### Current Coverage

- **SecurityManager**: ~95% coverage
- **MapReader**: ~90% coverage
- **PerfBufferReader**: ~85% coverage
- **PrometheusExporter**: ~90% coverage
- **Integration**: ~80% coverage

### Total Test Count

- **Unit tests**: ~200 tests
- **Integration tests**: ~50 tests
- **Total**: ~250 tests

## Contributing

When adding new features:

1. Write unit tests for new functionality
2. Write integration tests for component interaction
3. Update this README with new test information
4. Ensure all tests pass before committing
5. Maintain or improve test coverage

## License

This test suite is part of the x0tta6bl4 project and is licensed under the Apache-2.0 license.
