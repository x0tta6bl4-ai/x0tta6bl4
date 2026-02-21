import os
import runpy
import sys
import types
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from src.llm.local_llm import LocalLLM


def _local_llm_ns():
    path = Path(__file__).resolve().parents[2] / "src" / "llm" / "local_llm.py"
    return runpy.run_path(str(path))


@pytest.fixture
def mock_llama():
    with patch("src.llm.local_llm.LLAMA_AVAILABLE", True), \
         patch("src.llm.local_llm.Llama", create=True) as mock:
        yield mock


@pytest.fixture
def mock_os_path():
    with patch("os.path.exists") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def llm(mock_llama, mock_os_path):
    # Setup mock instance
    mock_instance = mock_llama.return_value
    # Mock __call__ for generate()
    mock_instance.side_effect = lambda prompt, **kwargs: {
        "choices": [{"text": "Mock response"}]
    }
    # Mock create_chat_completion
    mock_instance.create_chat_completion.return_value = {
        "choices": [{"message": {"content": "Mock chat response"}}]
    }
    return LocalLLM(model_path="mock_path", n_ctx=512)


class TestLocalLLM:
    def test_init_success(self, mock_llama, mock_os_path):
        """Test successful initialization"""
        llm = LocalLLM(model_path="test.gguf", n_ctx=1024)
        mock_llama.assert_called_once_with(
            model_path="test.gguf",
            n_ctx=1024,
            n_threads=1,  # Default
            n_batch=128,
            verbose=False,
            n_gpu_layers=0,
        )
        assert llm.model_path == "test.gguf"
        assert llm.llm is not None

    def test_init_file_not_found(self, mock_llama):
        """Test initialization when file doesn't exist"""
        with patch("os.path.exists", return_value=False):
            llm = LocalLLM(model_path="missing.gguf")
            mock_llama.assert_not_called()
            assert llm.llm is None

    def test_generate_success(self, llm):
        """Test successful text generation"""
        response = llm.generate("Test prompt")
        assert response == "Mock response"
        # self.llm is the mock_instance, which is called directly for generate
        llm.llm.assert_called()

    def test_generate_failure_model_not_loaded(self, mock_llama):
        """Test generation fails gracefully if model is None"""
        with patch("os.path.exists", return_value=False):
            llm = LocalLLM(model_path="missing.gguf")
            # Ensure llm is None
            llm.llm = None
            response = llm.generate("Test")
            assert "ERROR: Local LLM not initialized" in response

    def test_generate_api_error(self, llm):
        """Test generation handles API errors"""
        llm.llm.side_effect = Exception("API Error")
        response = llm.generate("Test")
        assert "Error generating text" in response

    def test_chat_completion_success(self, llm):
        """Test chat completion"""
        messages = [{"role": "user", "content": "Hello"}]
        response = llm.chat_completion(messages)
        assert response == "Mock chat response"
        llm.llm.create_chat_completion.assert_called_once()


def test_import_marks_llama_available_when_dependency_exists(monkeypatch):
    fake_module = types.ModuleType("llama_cpp")

    class _FakeLlama:
        pass

    fake_module.Llama = _FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)

    ns = _local_llm_ns()
    assert ns["LLAMA_AVAILABLE"] is True


def test_init_returns_early_when_llama_unavailable():
    with patch("src.llm.local_llm.LLAMA_AVAILABLE", False):
        instance = LocalLLM(model_path="unused.gguf")
    assert instance.llm is None


def test_init_uses_offline_fallback_and_verbose_logging(mock_llama):
    def _exists(path: str) -> bool:
        if path == "primary.gguf":
            return False
        if path == "gguf/llama-3.2-3b-q4.gguf":
            return True
        return False

    assert _exists("anything-else") is False

    with patch("src.llm.local_llm.LLAMA_AVAILABLE", True), patch(
        "os.path.exists", side_effect=_exists
    ):
        LocalLLM(model_path="primary.gguf", verbose=True)

    mock_llama.assert_called_once_with(
        model_path="gguf/llama-3.2-3b-q4.gguf",
        n_ctx=512,
        n_gpu_layers=0,
        verbose=True,
        n_threads=1,
        n_batch=128,
    )


def test_init_handles_llama_constructor_exception():
    with patch("src.llm.local_llm.LLAMA_AVAILABLE", True), patch(
        "os.path.exists", return_value=True
    ), patch("src.llm.local_llm.Llama", side_effect=RuntimeError("load-failed")):
        instance = LocalLLM(model_path="ok.gguf")
    assert instance.llm is None


def test_chat_completion_handles_uninitialized_and_runtime_error(mock_llama, mock_os_path):
    with patch("src.llm.local_llm.LLAMA_AVAILABLE", False):
        not_ready = LocalLLM(model_path="missing.gguf")
    assert not_ready.chat_completion([{"role": "user", "content": "hi"}]).startswith(
        "ERROR: Local LLM not initialized"
    )
    assert not_ready.is_ready() is False

    ready = LocalLLM(model_path="mock_path", n_ctx=256)
    ready.llm.create_chat_completion.side_effect = RuntimeError("chat boom")
    response = ready.chat_completion([{"role": "user", "content": "hi"}])
    assert "Error in chat completion" in response
    assert ready.is_ready() is True
