import logging
import os
from typing import Dict, List, Optional, Union

try:
    from llama_cpp import Llama

    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False
    Llama = None

logger = logging.getLogger(__name__)


class LocalLLM:
    """
    Wrapper for llama-cpp-python to run quantized LLMs locally on CPU.
    Designed for low-resource environments (e.g., Athlon 3000G, 16GB RAM).
    """

    def __init__(
        self,
        model_path: str = "models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        n_ctx: int = 512,  # Drastically reduced from 2048 for stability
        n_gpu_layers: int = 0,  # Keep CPU only
        n_threads: int = 1,  # Single thread to prevent system freeze
        n_batch: int = 128,  # Smaller batch size
        verbose: bool = False,
    ):
        self.model_path = model_path
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.n_threads = n_threads
        self.n_batch = n_batch
        self.verbose = verbose
        self.llm = None

        if not LLAMA_AVAILABLE:
            logger.warning("⚠️ llama-cpp-python not installed. Local LLM will not work.")
            return

        # Offline fallback check
        if not os.path.exists(model_path):
             # Fallback for offline/underserved regions
             offline_path = "gguf/llama-3.2-3b-q4.gguf"
             if os.path.exists(offline_path):
                 logger.info(f"⚠️ Primary model not found. Switching to offline backup: {offline_path}")
                 model_path = offline_path
             else:
                 logger.warning(f"⚠️ Model not found at {model_path}. Please download it.")
                 # Don't raise error, just log warning to allow app to start without model
                 return

        try:
            if verbose:
                logger.info(f"Loading Local LLM from {model_path}...")

            self.llm = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=verbose,
                n_threads=n_threads,
                n_batch=n_batch,
            )

            if verbose:
                logger.info("✅ Local LLM loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load Local LLM: {e}")
            self.llm = None

    def generate(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> str:
        """Raw text completion."""
        if not self.llm:
            return "ERROR: Local LLM not initialized"

        try:
            output = self.llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=["<|im_end|>", "<|endoftext|>"],
                echo=False,
            )
            return output["choices"][0]["text"]
        except Exception as e:
            logger.error(f"Generation error: {e}")
            return f"Error generating text: {str(e)}"

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> str:
        """Chat completion using model's chat template."""
        if not self.llm:
            return "ERROR: Local LLM not initialized"

        try:
            response = self.llm.create_chat_completion(
                messages=messages, max_tokens=max_tokens, temperature=temperature
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Chat completion error: {e}")
            return f"Error in chat completion: {str(e)}"

    def is_ready(self) -> bool:
        return self.llm is not None
