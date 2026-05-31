"""
SafeSubprocess - безопасная обёртка для subprocess вызовов.

Предотвращает command injection через строгую валидацию входных параметров.
"""

import logging
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Ошибка валидации параметров."""

    pass


class SecurityError(Exception):
    """Ошибка безопасности при выполнении команды."""

    pass


@dataclass
class SafeCommandResult:
    """Результат выполнения безопасной команды."""

    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: List[str]


class SafeSubprocess:
    """
    Безопасная обёртка для subprocess вызовов.

    Features:
    - Валидация всех параметров (только alphanumeric, dash, underscore, dot)
    - Запрет shell mode у subprocess
    - Таймауты по умолчанию
    - Логирование всех вызовов
    - Проверка разрешённых команд
    """

    # Разрешённые команды (whitelist)
    # Note: sh and bash are removed from allowed commands for security
    ALLOWED_COMMANDS = {
        "docker",
        "aws",
        "az",
        "gcloud",
        "kubectl",
        "helm",
        "git",
        "python3",
        "python",
        "pip",
        "pip3",
        "which",
        "where",
        "echo",
        "cat",
        "ipconfig",
        "iptables",
        "ls",
        "pwd",
        "resolvectl",
        "scutil",
        "sleep",
        "systemctl",
        "false",
        "true",
        "test",
    }

    TRUSTED_COMMAND_DIRS = {
        "/bin",
        "/usr/bin",
        "/usr/local/bin",
        "/sbin",
        "/usr/sbin",
    }

    REDACTED = "[REDACTED]"
    SENSITIVE_ARG_NAMES = {
        "--password",
        "--passwd",
        "--token",
        "--access-token",
        "--refresh-token",
        "--secret",
        "--client-secret",
        "--api-key",
        "--key",
        "--private-key",
    }
    STDIN_SECRET_FLAGS = {"--password-stdin"}
    SENSITIVE_VALUE_PATTERN = re.compile(
        r"(?i)\b([a-z0-9_.-]*(?:password|passwd|token|secret|api[_-]?key|"
        r"access[_-]?key|private[_-]?key|credential)[a-z0-9_.-]*)(=|:)[^\s,]+"
    )

    # Разрешённые символы в строковых параметрах
    SAFE_STRING_PATTERN = re.compile(r"^[a-zA-Z0-9._:@/+=~,()-]+$")

    # Максимальная длина параметра
    MAX_PARAM_LENGTH = 200

    # Дефолтный таймаут
    DEFAULT_TIMEOUT = 300  # 5 минут

    @classmethod
    def validate_safe_string(cls, value: str, param_name: str = "parameter") -> bool:
        """
        Проверка безопасности строки для использования в shell.

        Args:
            value: Значение для проверки
            param_name: Имя параметра (для логирования)

        Returns:
            True если строка безопасна

        Raises:
            ValidationError: Если строка не прошла валидацию
        """
        if not isinstance(value, str):
            raise ValidationError(f"{param_name} must be string, got {type(value)}")

        if not value:
            raise ValidationError(f"{param_name} cannot be empty")

        if len(value) > cls.MAX_PARAM_LENGTH:
            raise ValidationError(
                f"{param_name} too long: {len(value)} > {cls.MAX_PARAM_LENGTH}"
            )

        if not cls.SAFE_STRING_PATTERN.match(value):
            raise ValidationError(
                f"{param_name} contains unsafe characters: {value!r}. "
                "Only alphanumeric, dot, dash, underscore, colon, @, /, "
                "=, +, ~, comma, and parentheses allowed"
            )

        # Проверка на опасные последовательности
        dangerous_patterns = [
            "..",  # Path traversal
            "`",  # Command substitution
            "$",  # Variable expansion
            "|",  # Pipe
            "&",  # Background
            ";",  # Command separator
            "&&",  # AND operator
            "||",  # OR operator
        ]

        for pattern in dangerous_patterns:
            if pattern in value:
                raise ValidationError(
                    f"{param_name} contains dangerous pattern: {pattern}"
                )

        return True

    @classmethod
    def validate_command(cls, cmd: List[str]) -> None:
        """
        Валидация команды перед выполнением.

        Args:
            cmd: Список аргументов команды

        Raises:
            ValidationError: Если команда не прошла валидацию
            SecurityError: Если команда не в whitelist
        """
        if not isinstance(cmd, list):
            raise ValidationError("Command must be a list of strings")

        if not cmd:
            raise ValidationError("Command cannot be empty")

        # Проверка базовой команды
        cmd_name = cls._resolve_command_name(cmd[0])

        if cmd_name not in cls.ALLOWED_COMMANDS:
            raise SecurityError(
                f"Command '{cmd_name}' not in allowed list. "
                f"Allowed: {', '.join(sorted(cls.ALLOWED_COMMANDS))}"
            )

        # Валидация всех аргументов
        for i, arg in enumerate(cmd[1:], 1):
            cls.validate_safe_string(arg, f"arg[{i}]")

    @classmethod
    def _resolve_command_name(cls, base_cmd: str) -> str:
        if not isinstance(base_cmd, str):
            raise ValidationError(
                f"Command executable must be string, got {type(base_cmd)}"
            )

        if not base_cmd:
            raise ValidationError("Command executable cannot be empty")

        if "/" in base_cmd or "\\" in base_cmd:
            normalized_path = os.path.normpath(base_cmd)
            command_dir = os.path.dirname(normalized_path)
            cmd_name = os.path.basename(normalized_path)
            if (
                not os.path.isabs(normalized_path)
                or command_dir not in cls.TRUSTED_COMMAND_DIRS
            ):
                raise SecurityError(
                    "Command path is not trusted. Use a bare executable name "
                    f"or one of: {', '.join(sorted(cls.TRUSTED_COMMAND_DIRS))}"
                )
        else:
            cmd_name = base_cmd

        cls.validate_safe_string(cmd_name, "command")
        return cmd_name

    @classmethod
    def redact_sensitive_text(cls, value: object) -> str:
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        elif not isinstance(value, str):
            value = str(value)

        return cls.SENSITIVE_VALUE_PATTERN.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{cls.REDACTED}",
            value,
        )

    @classmethod
    def sanitize_command_for_log(cls, cmd: Sequence[str]) -> str:
        sanitized: List[str] = []
        redact_next = False

        for raw_arg in cmd:
            arg = str(raw_arg)
            lower_arg = arg.lower()

            if redact_next:
                sanitized.append(cls.REDACTED)
                redact_next = False
                continue

            if lower_arg in cls.STDIN_SECRET_FLAGS:
                sanitized.append(arg)
                continue

            if lower_arg in cls.SENSITIVE_ARG_NAMES:
                sanitized.append(arg)
                redact_next = True
                continue

            if any(
                lower_arg.startswith(f"{flag}=")
                for flag in cls.SENSITIVE_ARG_NAMES | cls.STDIN_SECRET_FLAGS
            ):
                key, _value = arg.split("=", 1)
                sanitized.append(f"{key}={cls.REDACTED}")
                continue

            sanitized.append(cls.redact_sensitive_text(arg))

        return " ".join(sanitized)

    @classmethod
    def run(
        cls,
        cmd: List[str],
        timeout: Optional[int] = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        input_data: Optional[str] = None,
    ) -> SafeCommandResult:
        """
        Безопасное выполнение команды.

        Args:
            cmd: Команда и аргументы (список строк)
            timeout: Таймаут в секундах (default: 300)
            capture_output: Перехватывать stdout/stderr
            text: Возвращать строки вместо bytes
            check: Выбрасывать исключение при ненулевом коде
            env: Переменные окружения
            cwd: Рабочая директория
            input_data: Данные для stdin

        Returns:
            SafeCommandResult с результатами

        Raises:
            ValidationError: При ошибке валидации
            SecurityError: При нарушении безопасности
            subprocess.TimeoutExpired: При таймауте
        """
        # Валидация
        cls.validate_command(cmd)

        # Установка таймаута
        if timeout is None:
            timeout = cls.DEFAULT_TIMEOUT

        if env is None:
            env = os.environ.copy()
            env["LC_ALL"] = "C"
            env["LANG"] = "C"

        # Логирование без раскрытия токенов, паролей и ключей.
        safe_command_for_log = cls.sanitize_command_for_log(cmd)
        logger.info(f"Executing: {safe_command_for_log}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=text,
                timeout=timeout,
                check=False,  # Мы сами обрабатываем код возврата
                env=env,
                cwd=cwd,
                input=input_data,
                shell=False,  # Критически важно!
            )

            success = result.returncode == 0

            if not success:
                logger.warning(
                    f"Command failed with code {result.returncode}: "
                    f"{safe_command_for_log}"
                )
                if result.stderr:
                    logger.warning(
                        f"Stderr: {cls.redact_sensitive_text(result.stderr[:500])}"
                    )
            else:
                logger.debug(f"Command succeeded: {safe_command_for_log}")

            if check and not success:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd, output=result.stdout, stderr=result.stderr
                )

            return SafeCommandResult(
                success=success,
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                command=cmd,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"Command timeout after {timeout}s: {safe_command_for_log}")
            raise
        except Exception as e:
            logger.error(
                "Command execution failed: %s", cls.redact_sensitive_text(str(e))
            )
            raise

    @classmethod
    def check_command(cls, command: str) -> bool:
        """
        Безопасная проверка наличия команды.

        Args:
            command: Имя команды

        Returns:
            True если команда доступна
        """
        try:
            cls.validate_safe_string(command, "command")

            check_cmd = ["which", command] if os.name != "nt" else ["where", command]
            result = cls.run(check_cmd, timeout=5)
            return result.success
        except (ValidationError, SecurityError):
            return False


# Удобные функции для частых операций


def safe_docker_tag(source: str, target: str) -> SafeCommandResult:
    """Безопасный docker tag."""
    return SafeSubprocess.run(["docker", "tag", source, target])


def safe_docker_push(image: str) -> SafeCommandResult:
    """Безопасный docker push."""
    return SafeSubprocess.run(["docker", "push", image], timeout=600)


def safe_helm_upgrade(
    release_name: str,
    chart_path: str,
    namespace: str = "default",
    values: Optional[Dict[str, str]] = None,
    timeout: int = 600,
) -> SafeCommandResult:
    """Безопасный helm upgrade --install."""
    cmd = [
        "helm",
        "upgrade",
        "--install",
        release_name,
        chart_path,
        "--namespace",
        namespace,
        "--create-namespace",
        "--wait",
        "--timeout",
        f"{timeout}s",
    ]

    if values:
        for key, value in values.items():
            cmd.extend(["--set", f"{key}={value}"])

    return SafeSubprocess.run(cmd, timeout=timeout + 60)


def safe_kubectl_wait(
    resource: str,
    namespace: str = "default",
    condition: str = "available",
    timeout: int = 300,
) -> SafeCommandResult:
    """Безопасный kubectl wait."""
    return SafeSubprocess.run(
        [
            "kubectl",
            "wait",
            f"--for=condition={condition}",
            resource,
            "--namespace",
            namespace,
            "--timeout",
            f"{timeout}s",
        ],
        timeout=timeout + 10,
    )
