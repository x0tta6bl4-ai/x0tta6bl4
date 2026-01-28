"""
Тесты для мета-когнитивного MAPE-K цикла
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch
from src.core.meta_cognitive_mape_k import (
    MetaCognitiveMAPEK,
    SolutionSpace,
    ReasoningPath,
    ReasoningMetrics,
    ReasoningAnalytics,
    ExecutionLogEntry,
    ReasoningApproach
)


class TestMetaCognitiveMAPEK:
    """Тесты для MetaCognitiveMAPEK"""
    
    @pytest.fixture
    def meta_mape_k(self):
        """Создание экземпляра MetaCognitiveMAPEK"""
        return MetaCognitiveMAPEK(node_id="test-node")
    
    @pytest.mark.asyncio
    async def test_meta_planning(self, meta_mape_k):
        """Тест мета-планирования"""
        task = {
            'type': 'test_task',
            'description': 'Test task description',
            'complexity': 0.5
        }
        
        solution_space, reasoning_path = await meta_mape_k.meta_planning(task)
        
        assert isinstance(solution_space, SolutionSpace)
        assert isinstance(reasoning_path, ReasoningPath)
        assert solution_space.selected_approach is not None
        assert len(solution_space.approaches) > 0
        assert reasoning_path.first_step is not None
    
    @pytest.mark.asyncio
    async def test_monitor(self, meta_mape_k):
        """Тест мониторинга с мета-осознанием"""
        result = await meta_mape_k.monitor()
        
        assert 'system_metrics' in result
        assert 'reasoning_metrics' in result
        assert isinstance(result['reasoning_metrics'], ReasoningMetrics)
    
    @pytest.mark.asyncio
    async def test_analyze(self, meta_mape_k):
        """Тест анализа с мета-рефлексией"""
        metrics = {
            'system_metrics': {'cpu_percent': 50.0},
            'reasoning_metrics': ReasoningMetrics()
        }
        
        result = await meta_mape_k.analyze(metrics)
        
        assert 'system_analysis' in result
        assert 'reasoning_analysis' in result
        assert 'efficiency' in result['reasoning_analysis']
    
    @pytest.mark.asyncio
    async def test_plan(self, meta_mape_k):
        """Тест планирования с мета-оптимизацией"""
        analysis = {
            'system_analysis': {'anomaly_detected': False},
            'reasoning_analysis': {'efficiency': 0.8, 'anomaly_detected': False}
        }
        
        result = await meta_mape_k.plan(analysis)
        
        assert 'recovery_plan' in result
        assert 'reasoning_optimization' in result
        assert 'approach_selection' in result['reasoning_optimization']
    
    @pytest.mark.asyncio
    async def test_execute(self, meta_mape_k):
        """Тест выполнения с мета-осознанием"""
        plan = {
            'recovery_plan': {
                'steps': [
                    {'action': 'test_action', 'description': 'Test step'}
                ]
            },
            'reasoning_optimization': {
                'approach_selection': ReasoningApproach.MAPE_K_ONLY.value
            }
        }
        
        result = await meta_mape_k.execute(plan)
        
        assert 'execution_result' in result
        assert 'execution_log' in result
        assert len(result['execution_log']) > 0
    
    @pytest.mark.asyncio
    async def test_knowledge(self, meta_mape_k):
        """Тест накопления знаний с мета-аналитикой"""
        execution_log = {
            'execution_result': {'status': 'success'},
            'execution_log': [
                {
                    'step': {'action': 'test'},
                    'result': {'status': 'success'},
                    'duration': 0.1,
                    'reasoning_approach': 'test_approach',
                    'meta_insights': {}
                }
            ]
        }
        
        result = await meta_mape_k.knowledge(execution_log)
        
        assert 'incident_record' in result
        assert 'reasoning_analytics' in result
        assert 'meta_insight' in result
        assert meta_mape_k.total_cycles > 0
    
    @pytest.mark.asyncio
    async def test_full_cycle(self, meta_mape_k):
        """Тест полного цикла"""
        task = {
            'type': 'test_cycle',
            'description': 'Test full cycle',
            'complexity': 0.5
        }
        
        result = await meta_mape_k.run_full_cycle(task)
        
        assert 'meta_plan' in result
        assert 'metrics' in result
        assert 'analysis' in result
        assert 'plan' in result
        assert 'execution_log' in result
        assert 'knowledge' in result
        assert 'error' not in result
    
    @pytest.mark.asyncio
    async def test_full_cycle_with_error(self, meta_mape_k):
        """Тест полного цикла с ошибкой"""
        # Создаем ситуацию, которая может вызвать ошибку
        with patch.object(meta_mape_k, 'meta_planning', side_effect=Exception("Test error")):
            result = await meta_mape_k.run_full_cycle({'type': 'error_test'})
            assert 'error' in result
    
    def test_reasoning_metrics(self, meta_mape_k):
        """Тест метрик рассуждения"""
        metrics = ReasoningMetrics()
        assert metrics.reasoning_time == 0.0
        assert metrics.approaches_tried == 0
        assert metrics.dead_ends_encountered == 0
    
    def test_solution_space(self):
        """Тест карты пространства решений"""
        space = SolutionSpace()
        assert len(space.approaches) == 0
        assert len(space.failure_history) == 0
    
    def test_reasoning_path(self):
        """Тест пути рассуждения"""
        path = ReasoningPath(first_step="test_step")
        assert path.first_step == "test_step"
        assert len(path.dead_ends_to_avoid) == 0


class TestReasoningApproach:
    """Тесты для ReasoningApproach"""
    
    def test_enum_values(self):
        """Тест значений enum"""
        assert ReasoningApproach.MAPE_K_ONLY.value == "mape_k_only"
        assert ReasoningApproach.RAG_SEARCH.value == "rag_search"
        assert ReasoningApproach.GRAPHSAGE_PREDICTION.value == "graphsage_prediction"
        assert ReasoningApproach.CAUSAL_ANALYSIS.value == "causal_analysis"
        assert ReasoningApproach.COMBINED_RAG_GRAPHSAGE.value == "combined_rag_graphsage"
        assert ReasoningApproach.COMBINED_ALL.value == "combined_all"


class TestExecutionLogEntry:
    """Тесты для ExecutionLogEntry"""
    
    def test_execution_log_entry(self):
        """Тест создания записи в журнале"""
        entry = ExecutionLogEntry(
            step={'action': 'test'},
            result={'status': 'success'},
            duration=0.1,
            reasoning_approach='test_approach',
            meta_insights={'test': 'value'}
        )
        
        assert entry.step == {'action': 'test'}
        assert entry.result == {'status': 'success'}
        assert entry.duration == 0.1
        assert entry.reasoning_approach == 'test_approach'
        assert 'test' in entry.meta_insights


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
