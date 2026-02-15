import os
from unittest.mock import ANY, MagicMock, patch

import pytest

from src.llm.local_llm import LocalLLM


@pytest.fixture
def mock_llama():
    with patch("src.llm.local_llm.Llama") as mock:
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
