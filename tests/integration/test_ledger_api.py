"""
Интеграционные тесты для Ledger API endpoints

Тестирование полного flow: индексирование → поиск → статус
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.core.app import app

client = TestClient(app)


@pytest.mark.asyncio
class TestLedgerAPI:
    """Тесты для Ledger API endpoints"""
    
    def test_ledger_status(self):
        """Тест получения статуса ledger"""
        response = client.get("/api/v1/ledger/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "indexed" in data
        assert "continuity_file" in data
        assert "file_exists" in data
        assert isinstance(data["indexed"], bool)
    
    def test_ledger_index(self):
        """Тест индексирования ledger"""
        response = client.post("/api/v1/ledger/index")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "indexed" in data
        assert data["indexed"] is True
    
    def test_ledger_search_post(self):
        """Тест semantic search через POST"""
        # Сначала индексируем
        client.post("/api/v1/ledger/index")
        
        # Затем ищем
        response = client.post(
            "/api/v1/ledger/search",
            json={
                "query": "Какие метрики у нас хуже targets?",
                "top_k": 5
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert "total_results" in data
        assert "search_time_ms" in data
        assert isinstance(data["results"], list)
        assert data["total_results"] >= 0
    
    def test_ledger_search_get(self):
        """Тест semantic search через GET"""
        # Сначала индексируем
        client.post("/api/v1/ledger/index")
        
        # Затем ищем
        response = client.get(
            "/api/v1/ledger/search",
            params={
                "q": "Какие метрики?",
                "top_k": 3
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "query" in data
        assert "results" in data
        assert data["query"] == "Какие метрики?"
    
    def test_ledger_search_empty_query(self):
        """Тест обработки пустого запроса"""
        response = client.post(
            "/api/v1/ledger/search",
            json={
                "query": "",
                "top_k": 5
            }
        )
        
        # Может быть 400 (bad request) или 200 с пустыми результатами
        assert response.status_code in [200, 400]
    
    def test_ledger_search_multiple_queries(self):
        """Тест множественных запросов"""
        # Индексируем
        client.post("/api/v1/ledger/index")
        
        queries = [
            "Какие метрики?",
            "Какие компоненты готовы?",
            "Что изменилось?"
        ]
        
        for query in queries:
            response = client.post(
                "/api/v1/ledger/search",
                json={"query": query, "top_k": 3}
            )
            assert response.status_code == 200
            assert response.json()["query"] == query


@pytest.mark.asyncio
class TestLedgerDriftAPI:
    """Тесты для Ledger Drift Detection API endpoints"""
    
    def test_drift_status(self):
        """Тест получения статуса drift detector"""
        response = client.get("/api/v1/ledger/drift/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "initialized" in data
        assert "continuity_file" in data
    
    def test_drift_detect(self):
        """Тест обнаружения расхождений"""
        response = client.post("/api/v1/ledger/drift/detect")
        assert response.status_code == 200
        
        data = response.json()
        assert "timestamp" in data
        assert "total_drifts" in data
        assert "drifts" in data
        assert isinstance(data["drifts"], list)

