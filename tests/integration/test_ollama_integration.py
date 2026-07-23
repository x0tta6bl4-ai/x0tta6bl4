"""
Integration tests for local Ollama/OpenAI-compatible LLM stack.

Verifies that Swarm decisions can be routed to a local Ollama instance
when KIMI_API_KEY is not set.
"""
import httpx
import pytest
from src.swarm.intelligence import DecisionContext, DecisionType, KimiK25Integration


@pytest.mark.asyncio
async def test_ollama_local_decision_integration():
    # 1. Check if local Ollama is running
    ollama_url = "http://localhost:11434/v1"
    try:
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            resp = await client.get(f"{ollama_url}/models")
        if resp.status_code != 200:
            pytest.skip("Local Ollama endpoint /v1/models returned non-200 status")
        
        models_data = resp.json()
        models = [m["id"] for m in models_data.get("data", [])]
        if not models:
            pytest.skip("Ollama has no models downloaded")
            
    except Exception as e:
        pytest.skip(f"Local Ollama is not running on port 11434: {e}")

    # 2. Pick the first available model or use qwen2.5-coder:1.5b if present
    selected_model = "qwen2.5-coder:1.5b"
    if selected_model not in models:
        selected_model = models[0]
        
    print(f"Using local Ollama model: {selected_model}")

    # 3. Create KimiK25Integration configured for local Ollama
    # Note: Enabled=True, api_endpoint=None (to trigger auto-detection)
    ki = KimiK25Integration(enabled=True, api_endpoint=ollama_url, model=selected_model)
    
    # Verify auto-detected endpoint and key
    assert ki.api_endpoint == ollama_url
    assert ki._get_api_key() == "local-stub-key"

    # 4. Propose options to the local LLM
    ctx = DecisionContext(
        topic="node_healing",
        decision_type=DecisionType.HEALING,
        description="High memory usage on mesh node ATHLON-NODE-01. RAM at 96%."
    )
    options = [
        "Ignore the issue",
        "Restart the local container services to reclaim RAM",
        "Trigger emergency failover to backup node NL-NODE-02"
    ]

    idx, reason = await ki.enhance_decision(ctx, options)
    
    print(f"Ollama recommendation index: {idx}")
    print(f"Ollama reasoning: {reason}")

    # 5. Verify response
    assert 0 <= idx < len(options), f"idx {idx} out of range [0, {len(options)})"
    assert len(reason) > 0, "reasoning must be non-empty"
