import os
import sys

import pytest

# Add project root to path
sys.path.append(os.getcwd())

from src.llm.local_llm import LLAMA_AVAILABLE, LocalLLM


@pytest.mark.skipif(not LLAMA_AVAILABLE, reason="llama-cpp-python not installed")
@pytest.mark.skipif(
    not os.path.exists("models/qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    reason="Model file not found",
)
def test_local_llm_generation():
    """Test basic text generation."""
    llm = LocalLLM(verbose=True)
    assert llm.is_ready()

    prompt = "Hello, I am a consciousness engine. Who are you?"
    response = llm.generate(prompt, max_tokens=20)

    print(f"\nPrompt: {prompt}\nResponse: {response}")
    assert isinstance(response, str)
    assert len(response) > 0
    assert "Error" not in response


@pytest.mark.skipif(not LLAMA_AVAILABLE, reason="llama-cpp-python not installed")
@pytest.mark.skipif(
    not os.path.exists("models/qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    reason="Model file not found",
)
def test_local_llm_chat():
    """Test chat completion."""
    llm = LocalLLM(verbose=True)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is 2+2?"},
    ]

    response = llm.chat_completion(messages, max_tokens=10)

    print(f"\nUser: What is 2+2?\nAssistant: {response}")
    assert isinstance(response, str)
    assert "4" in response or "four" in response.lower()
