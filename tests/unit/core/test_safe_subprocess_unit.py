import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")

"""Unit tests for src/core/safe_subprocess.py"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.core.safe_subprocess import (SafeCommandResult, SafeSubprocess,
                                      SecurityError, ValidationError,
                                      safe_docker_push, safe_docker_tag,
                                      safe_helm_upgrade, safe_kubectl_wait)

# ============================================================================
# SafeCommandResult tests
# ============================================================================


class TestSafeCommandResult:
    """Tests for SafeCommandResult dataclass."""

    def test_create_result(self):
        result = SafeCommandResult(
            success=True,
            returncode=0,
            stdout="ok",
            stderr="",
            command=["echo", "hello"],
        )
        assert result.success is True
        assert result.returncode == 0
        assert result.stdout == "ok"
        assert result.stderr == ""
        assert result.command == ["echo", "hello"]

    def test_failed_result(self):
        result = SafeCommandResult(
            success=False,
            returncode=1,
            stdout="",
            stderr="error message",
            command=["false"],
        )
        assert result.success is False
        assert result.returncode == 1
        assert result.stderr == "error message"


# ============================================================================
# ValidationError / SecurityError tests
# ============================================================================


class TestExceptions:
    """Tests for custom exception types."""

    def test_validation_error_is_exception(self):
        with pytest.raises(ValidationError):
            raise ValidationError("bad input")

    def test_security_error_is_exception(self):
        with pytest.raises(SecurityError):
            raise SecurityError("forbidden command")

    def test_validation_error_message(self):
        err = ValidationError("test message")
        assert str(err) == "test message"

    def test_security_error_message(self):
        err = SecurityError("security violation")
        assert str(err) == "security violation"


# ============================================================================
# validate_safe_string tests
# ============================================================================


class TestValidateSafeString:
    """Tests for SafeSubprocess.validate_safe_string."""

    def test_simple_alphanumeric(self):
        assert SafeSubprocess.validate_safe_string("hello123") is True

    def test_with_dots_and_dashes(self):
        assert SafeSubprocess.validate_safe_string("my-image.v1.0") is True

    def test_with_underscores(self):
        assert SafeSubprocess.validate_safe_string("my_image_name") is True

    def test_with_colons(self):
        assert SafeSubprocess.validate_safe_string("registry:5000") is True

    def test_with_at_sign(self):
        assert SafeSubprocess.validate_safe_string("user@host") is True

    def test_with_slashes(self):
        assert SafeSubprocess.validate_safe_string("registry/org/image") is True

    def test_with_equals_sign(self):
        assert SafeSubprocess.validate_safe_string("key=value") is True

    def test_docker_image_tag(self):
        assert SafeSubprocess.validate_safe_string("myrepo/myimage:v1.2.3") is True

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            SafeSubprocess.validate_safe_string("")

    def test_non_string_raises(self):
        with pytest.raises(ValidationError, match="must be string"):
            SafeSubprocess.validate_safe_string(123)

    def test_too_long_string_raises(self):
        long_string = "a" * 201
        with pytest.raises(ValidationError, match="too long"):
            SafeSubprocess.validate_safe_string(long_string)

    def test_max_length_exact(self):
        exact_string = "a" * 200
        assert SafeSubprocess.validate_safe_string(exact_string) is True

    def test_space_in_string_raises(self):
        with pytest.raises(ValidationError, match="unsafe characters"):
            SafeSubprocess.validate_safe_string("hello world")

    def test_newline_in_string_raises(self):
        with pytest.raises(ValidationError, match="unsafe characters"):
            SafeSubprocess.validate_safe_string("hello\nworld")

    def test_custom_param_name_in_error(self):
        with pytest.raises(ValidationError, match="my_param"):
            SafeSubprocess.validate_safe_string("", param_name="my_param")

    # --- Dangerous pattern tests ---

    def test_path_traversal_blocked(self):
        with pytest.raises(ValidationError, match="dangerous pattern"):
            SafeSubprocess.validate_safe_string("../../etc/passwd")

    def test_dollar_sign_blocked(self):
        """Dollar sign is not in SAFE_STRING_PATTERN, so caught by regex first."""
        with pytest.raises(ValidationError, match="unsafe characters"):
            SafeSubprocess.validate_safe_string("$HOME")

    def test_pipe_blocked(self):
        with pytest.raises(ValidationError, match="unsafe characters"):
            SafeSubprocess.validate_safe_string("cmd|evil")

    def test_ampersand_blocked(self):
        with pytest.raises(ValidationError, match="unsafe characters"):
            SafeSubprocess.validate_safe_string("cmd&bg")

    def test_semicolon_blocked(self):
        with pytest.raises(ValidationError, match="unsafe characters"):
            SafeSubprocess.validate_safe_string("cmd;evil")

    def test_backtick_blocked(self):
        with pytest.raises(ValidationError, match="unsafe characters"):
            SafeSubprocess.validate_safe_string("`whoami`")

    def test_double_dot_in_otherwise_safe_string(self):
        """Even if chars are safe, '..' pattern is caught."""
        with pytest.raises(ValidationError, match="dangerous pattern"):
            SafeSubprocess.validate_safe_string("path/to/../secret")


# ============================================================================
# validate_command tests
# ============================================================================


class TestValidateCommand:
    """Tests for SafeSubprocess.validate_command."""

    def test_allowed_command_docker(self):
        SafeSubprocess.validate_command(["docker", "ps"])

    def test_allowed_command_kubectl(self):
        SafeSubprocess.validate_command(["kubectl", "get", "pods"])

    def test_allowed_command_helm(self):
        SafeSubprocess.validate_command(["helm", "list"])

    def test_allowed_command_git(self):
        SafeSubprocess.validate_command(["git", "status"])

    def test_allowed_command_python3(self):
        SafeSubprocess.validate_command(["python3", "--version"])

    def test_allowed_command_with_path(self):
        """Command with full path: base name extracted."""
        SafeSubprocess.validate_command(["/usr/bin/docker", "ps"])

    def test_disallowed_command_bash(self):
        with pytest.raises(SecurityError, match="not in allowed list"):
            SafeSubprocess.validate_command(["bash", "-c", "rm -rf /"])

    def test_disallowed_command_sh(self):
        with pytest.raises(SecurityError, match="not in allowed list"):
            SafeSubprocess.validate_command(["sh", "-c", "evil"])

    def test_disallowed_command_rm(self):
        with pytest.raises(SecurityError, match="not in allowed list"):
            SafeSubprocess.validate_command(["rm", "-rf", "/"])

    def test_disallowed_command_curl(self):
        with pytest.raises(SecurityError, match="not in allowed list"):
            SafeSubprocess.validate_command(["curl", "http://evil.com"])

    def test_empty_command_raises(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            SafeSubprocess.validate_command([])

    def test_non_list_command_raises(self):
        with pytest.raises(ValidationError, match="must be a list"):
            SafeSubprocess.validate_command("docker ps")

    def test_command_with_unsafe_arg(self):
        with pytest.raises(ValidationError):
            SafeSubprocess.validate_command(["docker", "run", "image; rm -rf /"])

    def test_command_with_path_traversal_arg(self):
        with pytest.raises(ValidationError, match="dangerous pattern"):
            SafeSubprocess.validate_command(["docker", "run", "../../etc/passwd"])

    def test_all_allowed_commands_listed(self):
        """Ensure the whitelist contains expected safe commands."""
        expected = {
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
            "ls",
            "pwd",
            "sleep",
            "false",
            "true",
            "test",
        }
        assert SafeSubprocess.ALLOWED_COMMANDS == expected


# ============================================================================
# run() tests
# ============================================================================


class TestSafeSubprocessRun:
    """Tests for SafeSubprocess.run with mocked subprocess."""

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_successful_run(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="output", stderr="")
        result = SafeSubprocess.run(["echo", "hello"])
        assert result.success is True
        assert result.returncode == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.command == ["echo", "hello"]

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_failed_run(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        result = SafeSubprocess.run(["false"])
        assert result.success is False
        assert result.returncode == 1
        assert result.stderr == "error"

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_with_check_raises_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fail")
        with pytest.raises(subprocess.CalledProcessError):
            SafeSubprocess.run(["false"], check=True)

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_with_check_success_no_raise(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = SafeSubprocess.run(["true"], check=True)
        assert result.success is True

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_default_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        SafeSubprocess.run(["echo", "test"])
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 300

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_custom_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        SafeSubprocess.run(["echo", "test"], timeout=10)
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 10

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_shell_always_false(self, mock_run):
        """Shell injection prevention: shell=False always."""
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        SafeSubprocess.run(["echo", "test"])
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["shell"] is False

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_timeout_expired_propagates(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["sleep", "999"], timeout=5
        )
        with pytest.raises(subprocess.TimeoutExpired):
            SafeSubprocess.run(["sleep", "999"], timeout=5)

    def test_run_validates_command_first(self):
        """Disallowed command should never reach subprocess.run."""
        with pytest.raises(SecurityError):
            SafeSubprocess.run(["bash", "-c", "evil"])

    def test_run_validates_args(self):
        with pytest.raises(ValidationError):
            SafeSubprocess.run(["docker", "run", "image; rm -rf /"])

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_passes_env(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        custom_env = {"PATH": "/usr/bin", "HOME": "/root"}
        SafeSubprocess.run(["echo", "test"], env=custom_env)
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"] == custom_env

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_default_env_includes_lc_all(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        SafeSubprocess.run(["echo", "test"])
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"]["LC_ALL"] == "C"
        assert call_kwargs["env"]["LANG"] == "C"

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_passes_cwd(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        SafeSubprocess.run(["ls"], cwd="/tmp")
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/tmp"

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_passes_input_data(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        SafeSubprocess.run(["cat"], input_data="hello")
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["input"] == "hello"

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_handles_none_stdout_stderr(self, mock_run):
        """When stdout/stderr are None, result should default to empty string."""
        mock_run.return_value = MagicMock(returncode=0, stdout=None, stderr=None)
        result = SafeSubprocess.run(["echo", "test"])
        assert result.stdout == ""
        assert result.stderr == ""

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_run_generic_exception_propagates(self, mock_run):
        mock_run.side_effect = OSError("permission denied")
        with pytest.raises(OSError, match="permission denied"):
            SafeSubprocess.run(["echo", "test"])


# ============================================================================
# check_command tests
# ============================================================================


class TestCheckCommand:
    """Tests for SafeSubprocess.check_command."""

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_command_exists(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="/usr/bin/docker", stderr=""
        )
        assert SafeSubprocess.check_command("docker") is True

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_command_not_found(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        assert SafeSubprocess.check_command("docker") is False

    def test_check_unsafe_command_returns_false(self):
        """An unsafe command name should return False without calling subprocess."""
        assert SafeSubprocess.check_command("rm -rf /") is False

    def test_check_empty_command_returns_false(self):
        assert SafeSubprocess.check_command("") is False

    def test_check_command_with_path_traversal_returns_false(self):
        assert SafeSubprocess.check_command("../../bin/bash") is False


# ============================================================================
# Helper function tests
# ============================================================================


class TestSafeDockerTag:
    """Tests for safe_docker_tag helper."""

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_docker_tag(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = safe_docker_tag("myimage:v1", "registry/myimage:v1")
        assert result.success is True
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "tag", "myimage:v1", "registry/myimage:v1"]

    def test_docker_tag_unsafe_source_raises(self):
        with pytest.raises(ValidationError):
            safe_docker_tag("image; rm -rf /", "target:v1")


class TestSafeDockerPush:
    """Tests for safe_docker_push helper."""

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_docker_push(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = safe_docker_push("registry/image:v1.0")
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert cmd == ["docker", "push", "registry/image:v1.0"]

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_docker_push_timeout_is_600(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        safe_docker_push("image:latest")
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 600


class TestSafeHelmUpgrade:
    """Tests for safe_helm_upgrade helper."""

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_helm_upgrade_basic(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = safe_helm_upgrade("myrelease", "mychart")
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert "helm" == cmd[0]
        assert "upgrade" in cmd
        assert "--install" in cmd
        assert "myrelease" in cmd
        assert "mychart" in cmd
        assert "--namespace" in cmd
        assert "--create-namespace" in cmd
        assert "--wait" in cmd

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_helm_upgrade_custom_namespace(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        safe_helm_upgrade("rel", "chart", namespace="production")
        cmd = mock_run.call_args[0][0]
        ns_idx = cmd.index("--namespace")
        assert cmd[ns_idx + 1] == "production"

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_helm_upgrade_with_values(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        safe_helm_upgrade("rel", "chart", values={"image.tag": "v2.0", "replicas": "3"})
        cmd = mock_run.call_args[0][0]
        assert "--set" in cmd
        # Values should appear as key=value
        set_indices = [i for i, x in enumerate(cmd) if x == "--set"]
        assert len(set_indices) == 2

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_helm_upgrade_timeout_parameter(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        safe_helm_upgrade("rel", "chart", timeout=120)
        cmd = mock_run.call_args[0][0]
        assert "120s" in cmd
        # subprocess timeout should be 120 + 60 = 180
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 180


class TestSafeKubectlWait:
    """Tests for safe_kubectl_wait helper."""

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_kubectl_wait_basic(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = safe_kubectl_wait("deployment/myapp")
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "kubectl"
        assert "wait" in cmd
        assert "--for=condition=available" in cmd
        assert "deployment/myapp" in cmd

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_kubectl_wait_custom_namespace(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        safe_kubectl_wait("pod/mypod", namespace="staging")
        cmd = mock_run.call_args[0][0]
        ns_idx = cmd.index("--namespace")
        assert cmd[ns_idx + 1] == "staging"

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_kubectl_wait_custom_condition(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        safe_kubectl_wait("pod/mypod", condition="ready")
        cmd = mock_run.call_args[0][0]
        assert "--for=condition=ready" in cmd

    @patch("src.core.safe_subprocess.subprocess.run")
    def test_kubectl_wait_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        safe_kubectl_wait("deployment/app", timeout=60)
        cmd = mock_run.call_args[0][0]
        assert "60s" in cmd
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 70  # 60 + 10
