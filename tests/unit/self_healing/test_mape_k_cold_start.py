"""Verify startup independently of pytest's shared import cache."""
import subprocess
import sys
from unittest.mock import patch

import pytest

from src.self_healing.mape_k.executor import MAPEKExecutor


def test_executor_initializes_in_fresh_process():
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
from src.self_healing.mape_k.executor import MAPEKExecutor
assert 'src.self_healing.recovery.executor' not in sys.modules
executor = MAPEKExecutor()
assert executor.use_recovery_executor
assert executor.recovery_executor is not None
"""], capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_constructor_error_is_not_silently_hidden():
    with patch('src.self_healing.recovery.executor.RecoveryActionExecutor',
               side_effect=RuntimeError('invalid configuration')):
        with pytest.raises(RuntimeError, match='invalid configuration'):
            MAPEKExecutor()


def test_falsey_event_bus_is_forwarded():
    class Bus:
        def __bool__(self):
            return False

    bus = Bus()
    with patch('src.self_healing.recovery.executor.RecoveryActionExecutor') as factory:
        MAPEKExecutor(event_bus=bus)
    factory.assert_called_once_with(event_bus=bus)


def test_falsey_event_bus_is_preserved_by_real_executor():
    class Bus:
        def __bool__(self):
            return False

    bus = Bus()
    executor = MAPEKExecutor(event_bus=bus)
    assert executor.recovery_executor.event_bus is bus
