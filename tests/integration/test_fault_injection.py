import pytest
from fastapi.testclient import TestClient
from src.core.app import app
from src.database import db_circuit_breaker
from src.resilience.advanced_patterns import CircuitState

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_breakers():
    """Сброс состояний предохранителей перед каждым тестом."""
    with db_circuit_breaker.lock:
        db_circuit_breaker.state = CircuitState.CLOSED
        db_circuit_breaker.failure_count = 0
    yield

def test_db_circuit_breaker_opens_on_failures():
    """Проверка, что предохранитель открывается при ошибках."""
    # 1. Имитируем падения (вызываем внутренний метод _on_failure)
    for _ in range(db_circuit_breaker.config.failure_threshold):
        db_circuit_breaker._on_failure()
    
    # 2. Теперь Circuit Breaker должен быть OPEN
    assert db_circuit_breaker.state == CircuitState.OPEN
    
    # 3. При попытке реального запроса (даже если БД жива), 
    # события SQLAlchemy (before_cursor_execute) должны заблокировать запрос.
    # Но так как TestClient не всегда пробрасывает события в SQLite в памяти корректно,
    # мы проверяем логику на уровне приложения.
    
    # В нашем database/__init__.py прописано:
    # raise sa_exc.OperationalError(..., Exception("Database Circuit Breaker is OPEN..."))
    
    with pytest.raises(Exception) as excinfo:
        from sqlalchemy import text
        from src.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    
    assert "Circuit Breaker is OPEN" in str(excinfo.value)

def test_security_headers_present():
    """Проверка, что новые заголовки безопасности присутствуют в ответе."""
    response = client.get("/health")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" in response.headers
    assert response.headers["Server"] == "x0tta6bl4-gateway"

def test_cors_headers_handling():
    """Проверка CORS логики."""
    # OPTIONS запрос (Preflight)
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
