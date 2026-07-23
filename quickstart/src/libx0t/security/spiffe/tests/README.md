# SPIFFE/SPIRE Tests

## Test Coverage

### Unit Tests
- ✅ `test_spiffe_auto_renew.py` - Auto-renewal functionality
- ⚠️ Additional unit tests can be added for:
  - Certificate validation
  - Process management
  - gRPC connection handling

### Integration Tests
- ⚠️ Integration tests require SPIRE Server/Agent running
- Can be added for:
  - End-to-end identity provisioning
  - mTLS connection establishment
  - Trust domain federation

## Running Tests

```bash
# Unit tests (no SPIRE required)
pytest tests/unit/test_spiffe_auto_renew.py

# Integration tests (requires SPIRE)
pytest tests/integration/test_spiffe_integration.py
```

## Test Requirements

- `pytest`
- `pytest-asyncio` (for async tests)
- SPIRE binaries (for integration tests only)

