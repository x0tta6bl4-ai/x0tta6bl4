"""Unit tests for src.agents.development.spec_to_code_agent."""

from __future__ import annotations

import pytest

from src.agents.development.spec_to_code_agent import (
    CodeLanguage,
    CodeType,
    Specification,
    SpecToCodeAgent,
    get_spec_to_code_agent,
)


def _spec(language: CodeLanguage = CodeLanguage.PYTHON) -> Specification:
    return Specification(
        name="mesh-health-service",
        description="Reports mesh health state.",
        language=language,
        code_type=CodeType.SERVICE,
        requirements=["return status", "include timestamp"],
    )


@pytest.mark.asyncio
async def test_python_template_is_real_compilable_code():
    generated = await SpecToCodeAgent().generate(_spec(CodeLanguage.PYTHON))

    assert "TODO" not in generated.code
    assert "pass" not in generated.code
    assert "class MeshHealthService" in generated.code
    assert "async def execute" in generated.code
    compile(generated.code, "<generated>", "exec")
    assert generated.quality_score == 0.85
    assert generated.metadata["generated_by"] == "spec_to_code_agent"


@pytest.mark.asyncio
async def test_non_python_templates_do_not_return_todo_placeholders():
    for language in (
        CodeLanguage.JAVASCRIPT,
        CodeLanguage.TYPESCRIPT,
        CodeLanguage.GO,
        CodeLanguage.RUST,
        CodeLanguage.JAVA,
    ):
        generated = await SpecToCodeAgent().generate(_spec(language))

        assert "TODO" not in generated.code
        assert "Implement" not in generated.code
        assert "mesh-health-service" in generated.code
        assert "return status" in generated.code


def test_class_name_is_safe_for_numeric_or_symbol_names():
    agent = SpecToCodeAgent()

    assert agent._class_name("123 bad-name") == "Generated123BadName"
    assert agent._class_name("!!!") == "Generated"


def test_get_spec_to_code_agent_returns_singleton():
    first = get_spec_to_code_agent()
    second = get_spec_to_code_agent()

    assert first is second
