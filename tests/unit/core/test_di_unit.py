"""
Unit tests for Dependency Injection container (src/core/di.py).
"""
import pytest
from src.core.di import DependencyContainer, get_container, container


class SimpleService:
    def __init__(self, value: int = 42):
        self.value = value


def test_register_and_resolve_singleton():
    di = DependencyContainer()
    service = SimpleService()
    di.register_singleton(SimpleService, service)

    resolved = di.resolve(SimpleService)
    assert resolved is service
    assert resolved.value == 42


def test_register_and_resolve_by_string():
    di = DependencyContainer()
    di.register_singleton("my_service", SimpleService(100))

    resolved = di.resolve("my_service")
    assert isinstance(resolved, SimpleService)
    assert resolved.value == 100


def test_register_factory():
    di = DependencyContainer()
    di.register_factory(SimpleService, lambda: SimpleService(77))

    resolved1 = di.resolve(SimpleService)
    resolved2 = di.resolve(SimpleService)

    assert resolved1 is not resolved2
    assert resolved1.value == 77
    assert resolved2.value == 77


def test_not_registered_raises_value_error():
    di = DependencyContainer()
    with pytest.raises(ValueError, match="Dependency not registered"):
        di.resolve("non_existent")


def test_global_container():
    c = get_container()
    assert c is container
