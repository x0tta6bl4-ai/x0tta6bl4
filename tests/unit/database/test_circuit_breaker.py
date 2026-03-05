from src.database import db_circuit_breaker
from src.resilience.advanced_patterns import CircuitState

def test_db_circuit_breaker_state_transitions():
    """Проверяет логику переходов состояний предохранителя БД без реального подключения."""
    # 1. Reset CB state
    with db_circuit_breaker.lock:
        db_circuit_breaker.state = CircuitState.CLOSED
        db_circuit_breaker.failure_count = 0
        db_circuit_breaker.success_count = 0
        db_circuit_breaker.config.failure_threshold = 2
        db_circuit_breaker.config.recovery_timeout_seconds = 1 # короткий таймаут для теста
        db_circuit_breaker.config.success_threshold = 1 # Одно успешное выполнение для закрытия

    # 2. Simulate failures
    db_circuit_breaker._on_failure()
    assert db_circuit_breaker.state == CircuitState.CLOSED
    
    db_circuit_breaker._on_failure()
    # Now CB should be OPEN
    assert db_circuit_breaker.state == CircuitState.OPEN

    # 3. Simulate recovery attempt (should fail immediately if timeout not reached)
    assert db_circuit_breaker._should_attempt_recovery() is False
    
    from datetime import datetime, timedelta
    # 4. Fast forward time to simulate timeout expiration
    db_circuit_breaker.last_failure_time = datetime.utcnow() - timedelta(seconds=2)
    
    # Now it should allow recovery attempt
    assert db_circuit_breaker._should_attempt_recovery() is True
    
    # 5. Simulate success during HALF_OPEN
    db_circuit_breaker.state = CircuitState.HALF_OPEN
    db_circuit_breaker._on_success()
    
    assert db_circuit_breaker.state == CircuitState.CLOSED
    assert db_circuit_breaker.failure_count == 0
