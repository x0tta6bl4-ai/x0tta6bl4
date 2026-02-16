"""
Identity Normalization Module - CVE-2020-12812 Protection

Архитектурное требование безопасности: все идентификаторы в x0tta6bl4
используют исключительно нижний регистр для предотвращения атак класса CVE-2020-12812.

Урок FortiGate: несоответствие обработки регистра между системами создаёт
обходы аутентификации, которые криптография не может исправить.

Решение x0tta6bl4: каноническая нормализация на архитектурном уровне.
"""

import hashlib
import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Архитектурные константы
X0TTA6BL4_IDENTIFIER = "x0tta6bl4"
HIP3_14CIRZ_IDENTIFIER = "hip3.14cirz"

# Разрешённые паттерны идентификаторов (только нижний регистр, цифры, точки, дефисы)
VALID_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9._-]+$")


def normalize_identity(identifier: str) -> Tuple[bytes, str]:
    """
    Нормализует идентификатор в каноническую форму (только нижний регистр).

    Это архитектурное требование безопасности для предотвращения атак класса CVE-2020-12812,
    где манипуляция регистром создаёт обходы аутентификации.

    Args:
        identifier: Исходный идентификатор (может содержать заглавные буквы)

    Returns:
        Tuple[bytes, str]: (канонический хеш, нормализованная строка)

    Raises:
        ValueError: Если идентификатор содержит недопустимые символы после нормализации
    """
    if not identifier:
        raise ValueError("Identifier cannot be empty")

    # Нормализация: только нижний регистр, обрезка пробелов
    canonical = identifier.lower().strip()

    # Валидация: только разрешённые символы
    if not VALID_IDENTIFIER_PATTERN.match(canonical):
        raise ValueError(
            f"Invalid identifier '{identifier}': only lowercase letters, "
            f"digits, dots, underscores, and hyphens allowed"
        )

    # Генерация канонического токена идентичности (SHA256 хеш)
    identity_token = hashlib.sha256(canonical.encode("utf-8")).digest()

    return identity_token, canonical


def validate_identifier(identifier: str) -> bool:
    """
    Валидирует идентификатор на соответствие архитектурным требованиям.

    Проверяет:
    1. Только нижний регистр
    2. Разрешённые символы (a-z, 0-9, ., _, -)
    3. Не пустой

    Args:
        identifier: Идентификатор для проверки

    Returns:
        bool: True если валиден, False иначе
    """
    if not identifier:
        return False

    normalized = identifier.lower().strip()

    # Проверка: идентификатор уже в нижнем регистре
    if identifier != normalized:
        logger.warning(
            f"⚠️ CVE-2020-12812 protection: identifier '{identifier}' contains uppercase. "
            f"Use '{normalized}' instead."
        )
        return False

    # Проверка паттерна
    return bool(VALID_IDENTIFIER_PATTERN.match(normalized))


def enforce_lowercase_rule(identifier: str, context: str = "identity") -> str:
    """
    Принудительно применяет правило нижнего регистра.

    Если идентификатор содержит заглавные буквы, отклоняет с ошибкой.
    Это fail-closed подход: лучше отказать доступ, чем создать обход безопасности.

    Args:
        identifier: Идентификатор для проверки
        context: Контекст использования (для логирования)

    Returns:
        str: Нормализованный идентификатор

    Raises:
        ValueError: Если идентификатор содержит заглавные буквы
    """
    if identifier != identifier.lower():
        error_msg = (
            f"❌ CVE-2020-12812 protection violation: '{identifier}' contains uppercase. "
            f"x0tta6bl4 requires all identifiers in lowercase only. "
            f"Context: {context}"
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    return identifier.lower().strip()


def get_identity_hash(identifier: str) -> str:
    """
    Получить канонический хеш идентификатора для использования в криптографических операциях.

    Гарантирует, что "jsmith", "Jsmith", "JSMITH" → один токен.

    Args:
        identifier: Идентификатор

    Returns:
        str: Hex-представление SHA256 хеша
    """
    _, canonical = normalize_identity(identifier)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Специальные идентификаторы системы (только нижний регистр)
SYSTEM_IDENTIFIERS = {
    "x0tta6bl4": X0TTA6BL4_IDENTIFIER,
    "hip3.14cirz": HIP3_14CIRZ_IDENTIFIER,
}


def is_system_identifier(identifier: str) -> bool:
    """
    Проверяет, является ли идентификатор системным (x0tta6bl4 или hip3.14cirz).

    Args:
        identifier: Идентификатор для проверки

    Returns:
        bool: True если системный идентификатор
    """
    normalized = identifier.lower().strip()
    return normalized in SYSTEM_IDENTIFIERS.values()
