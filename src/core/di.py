"""
Dependency Injection (DI) Container for x0tta6bl4 core components.

Allows decoupled resolution of services to break cyclic dependencies.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Type, TypeVar, overload

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DependencyContainer:
    """
    Легковесный потокобезопасный контейнер внедрения зависимостей.
    Поддерживает регистрацию синглтонов и фабрик.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._instances: Dict[Any, Any] = {}
        self._factories: Dict[Any, Callable[[], Any]] = {}

    def register_singleton(self, key: Any, instance: Any) -> None:
        """Зарегистрировать готовый синглтон-объект."""
        with self._lock:
            self._instances[key] = instance
            # Удаляем фабрику, если она была зарегистрирована ранее для этого ключа
            self._factories.pop(key, None)
        logger.debug(f"Registered singleton dependency: {key}")

    def register_factory(self, key: Any, factory: Callable[[], Any]) -> None:
        """Зарегистрировать фабрику для создания нового объекта при каждом вызове resolve()."""
        with self._lock:
            self._factories[key] = factory
            self._instances.pop(key, None)
        logger.debug(f"Registered factory dependency: {key}")

    @overload
    def resolve(self, key: Type[T]) -> T: ...

    @overload
    def resolve(self, key: str) -> Any: ...

    def resolve(self, key: Any) -> Any:
        """
        Разрешить зависимость по ключу (классу или строке).
        Выбрасывает ValueError, если зависимость не найдена.
        """
        with self._lock:
            if key in self._instances:
                return self._instances[key]

            if key in self._factories:
                factory = self._factories[key]
                # Фабрика создаёт новый объект при каждом вызове (transient scope).
                instance = factory()
                return instance

        raise ValueError(f"Dependency not registered: {key}")

    def has(self, key: Any) -> bool:
        """Проверить, зарегистрирована ли зависимость."""
        with self._lock:
            return key in self._instances or key in self._factories

    def clear(self) -> None:
        """Очистить все зарегистрированные зависимости."""
        with self._lock:
            self._instances.clear()
            self._factories.clear()


# Глобальный экземпляр контейнера для простого доступа
container = DependencyContainer()


def get_container() -> DependencyContainer:
    """Получить глобальный экземпляр DependencyContainer."""
    return container
