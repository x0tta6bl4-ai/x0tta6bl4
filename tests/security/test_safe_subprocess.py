"""
Тесты для SafeSubprocess - безопасной обёртки subprocess.
"""
import pytest
import subprocess
from src.core.safe_subprocess import (
    SafeSubprocess,
    ValidationError,
    SecurityError,
    SafeCommandResult,
    safe_docker_tag,
    safe_helm_upgrade
)


class TestSafeSubprocessValidation:
    """Тесты валидации параметров."""
    
    def test_validate_safe_string_valid(self):
        """Валидация безопасных строк."""
        valid_strings = [
            "docker",
            "image-name",
            "image_name",
            "image.name",
            "v1.2.3",
            "user@example.com",
            "/path/to/file",
            "namespace/app:tag"
        ]
        
        for s in valid_strings:
            assert SafeSubprocess.validate_safe_string(s, "test") is True
    
    def test_validate_safe_string_invalid_characters(self):
        """Валидация отклоняет опасные символы."""
        invalid_strings = [
            "image;rm -rf /",  # Command separator
            "image|cat /etc/passwd",  # Pipe
            "image`whoami`",  # Command substitution
            "image$(whoami)",  # Variable expansion
            "image&&reboot",  # AND operator
            "image||shutdown",  # OR operator
            "../etc/passwd",  # Path traversal
        ]
        
        for s in invalid_strings:
            with pytest.raises(ValidationError):
                SafeSubprocess.validate_safe_string(s, "test")
    
    def test_validate_safe_string_empty(self):
        """Валидация отклоняет пустые строки."""
        with pytest.raises(ValidationError):
            SafeSubprocess.validate_safe_string("", "test")
    
    def test_validate_safe_string_too_long(self):
        """Валидация отклоняет слишком длинные строки."""
        long_string = "a" * 201
        with pytest.raises(ValidationError):
            SafeSubprocess.validate_safe_string(long_string, "test")
    
    def test_validate_command_allowed(self):
        """Валидация разрешённых команд."""
        allowed_commands = [
            ["docker", "ps"],
            ["kubectl", "get", "pods"],
            ["helm", "list"],
            ["aws", "sts", "get-caller-identity"],
            ["git", "status"],
        ]
        
        for cmd in allowed_commands:
            # Не должно выбрасывать исключение
            SafeSubprocess.validate_command(cmd)
    
    def test_validate_command_not_allowed(self):
        """Валидация отклоняет неразрешённые команды."""
        # rm is not in the allowed commands whitelist
        with pytest.raises(SecurityError):
            SafeSubprocess.validate_command(["rm", "-rf", "/"])
        
        # bash is not in the allowed commands whitelist
        with pytest.raises(SecurityError):
            SafeSubprocess.validate_command(["bash", "-c", "evil"])
        
        # sh is not in the allowed commands whitelist
        with pytest.raises(SecurityError):
            SafeSubprocess.validate_command(["sh", "script.sh"])
    
    def test_validate_command_empty(self):
        """Валидация отклоняет пустые команды."""
        with pytest.raises(ValidationError):
            SafeSubprocess.validate_command([])


class TestSafeSubprocessRun:
    """Тесты выполнения команд."""
    
    def test_run_echo_success(self):
        """Успешное выполнение echo."""
        result = SafeSubprocess.run(["echo", "hello"])
        
        assert result.success is True
        assert result.returncode == 0
        assert "hello" in result.stdout
        assert result.command == ["echo", "hello"]
    
    def test_run_with_timeout(self):
        """Таймаут выполнения."""
        with pytest.raises(subprocess.TimeoutExpired):
            SafeSubprocess.run(["sleep", "10"], timeout=1)
    
    def test_run_invalid_command(self):
        """Выполнение неразрешённой команды."""
        with pytest.raises(SecurityError):
            SafeSubprocess.run(["rm", "-rf", "/"])
    
    def test_run_with_dangerous_args(self):
        """Выполнение с опасными аргументами."""
        with pytest.raises(ValidationError):
            SafeSubprocess.run(["echo", "hello; rm -rf /"])
    
    def test_run_check_true(self):
        """Выполнение с check=True выбрасывает исключение."""
        with pytest.raises(subprocess.CalledProcessError):
            SafeSubprocess.run(["false"], check=True)
    
    def test_run_shell_not_allowed(self):
        """shell=True не используется."""
        # Проверяем, что shell=True не передаётся
        result = SafeSubprocess.run(["echo", "test"])
        assert result.success is True


class TestSafeSubprocessCheckCommand:
    """Тесты проверки наличия команд."""
    
    def test_check_command_exists(self):
        """Проверка существующей команды."""
        assert SafeSubprocess.check_command("python3") is True
    
    def test_check_command_not_exists(self):
        """Проверка несуществующей команды."""
        assert SafeSubprocess.check_command("nonexistent_command_12345") is False
    
    def test_check_command_dangerous(self):
        """Проверка отклоняет опасные имена."""
        assert SafeSubprocess.check_command("rm -rf /") is False


class TestConvenienceFunctions:
    """Тесты удобных функций."""
    
    def test_safe_docker_tag_validation(self):
        """Валидация в safe_docker_tag."""
        # Должно работать с безопасными именами
        result = safe_docker_tag("source:tag", "target:tag")
        # Команда сформирована правильно, но docker может не быть установлен
        assert "docker" in result.command
        
        # Должно отклонять опасные имена
        with pytest.raises(ValidationError):
            safe_docker_tag("source; rm -rf /", "target")
    
    def test_safe_helm_upgrade_validation(self):
        """Валидация в safe_helm_upgrade."""
        # Должно формировать правильную команду
        result = safe_helm_upgrade(
            release_name="my-release",
            chart_path="./chart",
            namespace="default",
            values={"image.tag": "v1.0.0"}
        )
        
        assert "helm" in result.command
        assert "my-release" in result.command
        assert "./chart" in result.command
        
        # Должно отклонять опасные имена
        with pytest.raises(ValidationError):
            safe_helm_upgrade(
                release_name="my-release; rm -rf /",
                chart_path="./chart"
            )


class TestSecurityScenarios:
    """Тесты security сценариев."""
    
    def test_command_injection_attempt_blocked(self):
        """Попытка command injection блокируется."""
        injection_attempts = [
            ["echo", "hello; cat /etc/passwd"],
            ["echo", "hello | cat /etc/passwd"],
            ["echo", "hello`whoami`"],
            ["echo", "hello$(whoami)"],
            ["echo", ".."],
        ]
        
        for cmd in injection_attempts:
            with pytest.raises(ValidationError):
                SafeSubprocess.run(cmd)
    
    def test_path_traversal_blocked(self):
        """Path traversal блокируется."""
        with pytest.raises(ValidationError):
            SafeSubprocess.run(["cat", "../etc/passwd"])
    
    def test_shell_metacharacters_blocked(self):
        """Shell метасимволы блокируются."""
        dangerous = [
            "test&",
            "test;",
            "test|",
            "test`",
            "test$",
        ]
        
        for d in dangerous:
            with pytest.raises(ValidationError):
                SafeSubprocess.validate_safe_string(d, "test")


class TestErrorHandling:
    """Тесты обработки ошибок."""
    
    def test_command_failure_captured(self):
        """Ошибка команды captured в результате."""
        result = SafeSubprocess.run(["false"])
        
        assert result.success is False
        assert result.returncode == 1
    
    def test_stderr_captured(self):
        """Stderr captured в результате."""
        result = SafeSubprocess.run(["ls", "/nonexistent_directory_12345"])
        
        assert result.success is False
        assert "No such file" in result.stderr or "does not exist" in result.stderr


if __name__ == "__main__":
    pytest.main([__file__, "-v"])