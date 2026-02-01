"""
SafeSubprocess - безопасная обёртка для subprocess вызовов.

Предотвращает command injection через строгую валидацию входных параметров.
"""
import os
import re
import subprocess
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass

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
    - Запрет shell=True
    - Таймауты по умолчанию
    - Логирование всех вызовов
    - Проверка разрешённых команд
    """
    
    # Разрешённые команды (whitelist)
    # Note: sh and bash are removed from allowed commands for security
    ALLOWED_COMMANDS = {
        'docker', 'aws', 'az', 'gcloud', 'kubectl', 'helm',
        'git', 'python3', 'python', 'pip', 'pip3',
        'which', 'where', 'echo', 'cat', 'ls', 'pwd',
        'sleep', 'false', 'true', 'test'
    }
    
    # Разрешённые символы в строковых параметрах
    SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9._:@/=-]+$')
    
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
                f"Only alphanumeric, dot, dash, underscore, colon, @, / allowed"
            )
            
        # Проверка на опасные последовательности
        dangerous_patterns = [
            '..',  # Path traversal
            '`',   # Command substitution
            '$',   # Variable expansion
            '|',   # Pipe
            '&',   # Background
            ';',   # Command separator
            '&&',  # AND operator
            '||',  # OR operator
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
        if not cmd:
            raise ValidationError("Command cannot be empty")
            
        if not isinstance(cmd, list):
            raise ValidationError("Command must be a list of strings")
            
        # Проверка базовой команды
        base_cmd = cmd[0]
        
        # Извлекаем имя команды из пути
        cmd_name = base_cmd.split('/')[-1]
        
        if cmd_name not in cls.ALLOWED_COMMANDS:
            raise SecurityError(
                f"Command '{cmd_name}' not in allowed list. "
                f"Allowed: {', '.join(sorted(cls.ALLOWED_COMMANDS))}"
            )
            
        # Валидация всех аргументов
        for i, arg in enumerate(cmd[1:], 1):
            cls.validate_safe_string(arg, f"arg[{i}]")
    
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
        input_data: Optional[str] = None
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
            
        # Логирование (безопасное)
        logger.info(f"Executing: {' '.join(cmd)}")
        
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
                shell=False  # Критически важно!
            )
            
            success = result.returncode == 0
            
            if not success:
                logger.warning(
                    f"Command failed with code {result.returncode}: {' '.join(cmd)}"
                )
                if result.stderr:
                    logger.warning(f"Stderr: {result.stderr[:500]}")
            else:
                logger.debug(f"Command succeeded: {' '.join(cmd)}")
                
            if check and not success:
                raise subprocess.CalledProcessError(
                    result.returncode, cmd,
                    output=result.stdout,
                    stderr=result.stderr
                )
                
            return SafeCommandResult(
                success=success,
                returncode=result.returncode,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                command=cmd
            )
            
        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timeout after {timeout}s: {' '.join(cmd)}")
            raise
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
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
    return SafeSubprocess.run([
        "docker", "tag",
        source,
        target
    ])


def safe_docker_push(image: str) -> SafeCommandResult:
    """Безопасный docker push."""
    return SafeSubprocess.run([
        "docker", "push",
        image
    ], timeout=600)


def safe_helm_upgrade(
    release_name: str,
    chart_path: str,
    namespace: str = "default",
    values: Optional[Dict[str, str]] = None,
    timeout: int = 600
) -> SafeCommandResult:
    """Безопасный helm upgrade --install."""
    cmd = [
        "helm", "upgrade", "--install",
        release_name,
        chart_path,
        "--namespace", namespace,
        "--create-namespace",
        "--wait",
        "--timeout", f"{timeout}s"
    ]
    
    if values:
        for key, value in values.items():
            cmd.extend(["--set", f"{key}={value}"])
            
    return SafeSubprocess.run(cmd, timeout=timeout + 60)


def safe_kubectl_wait(
    resource: str,
    namespace: str = "default",
    condition: str = "available",
    timeout: int = 300
) -> SafeCommandResult:
    """Безопасный kubectl wait."""
    return SafeSubprocess.run([
        "kubectl", "wait",
        f"--for=condition={condition}",
        resource,
        "--namespace", namespace,
        "--timeout", f"{timeout}s"
    ], timeout=timeout + 10)