from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from src.resilience.advanced_patterns import CircuitBreaker, CircuitState

db_cb = CircuitBreaker(failure_threshold=3, recovery_timeout=2)
engine = create_engine("sqlite:///:memory:")

@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    with db_cb.lock:
        if db_cb.state == CircuitState.OPEN:
            if db_cb._should_attempt_recovery():
                db_cb.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Database Circuit Breaker is OPEN")

@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    db_cb._on_success()

@event.listens_for(engine, "handle_error")
def handle_error(exception_context):
    # Only react to connection/operational errors, not data errors like UniqueViolation
    if isinstance(exception_context.original_exception, OperationalError):
        db_cb._on_failure()

print("Events registered")
