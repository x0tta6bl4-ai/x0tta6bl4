from __future__ import annotations
# 🤖 Spec-to-Code Agent - x0tta6bl4
"""
AI Agent for generating code from specifications.
"""

import logging
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


class CodeLanguage(str, Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"


class CodeType(str, Enum):
    """Type of code to generate."""
    API = "api"
    MODEL = "model"
    SERVICE = "service"
    CONTROLLER = "controller"
    UTILITY = "utility"
    TEST = "test"


@dataclass
class Specification:
    """Code specification."""
    name: str
    description: str
    language: CodeLanguage
    code_type: CodeType
    requirements: list[str] = field(default_factory=list)
    constraints: Optional[dict] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class GeneratedCode:
    """Generated code result."""
    code: str
    language: CodeLanguage
    code_type: CodeType
    specification: Specification
    timestamp: datetime = field(default_factory=datetime.utcnow)
    quality_score: float = 0.0
    metadata: dict = field(default_factory=dict)


class SpecToCodeAgent:
    """
    Spec-to-Code Agent - генерирует код из спецификаций.
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Инициализация агента.
        
        Args:
            config: Конфигурация
        """
        self.config = config or {}
        self.is_initialized = False
        self.thinking_coach = AgentThinkingCoach(
            agent_id="spec-to-code",
            role="development",
            capabilities=("code_generation", "planning", "rag"),
        )
        self.last_thinking_context: Optional[dict] = None
        logger.info("SpecToCodeAgent initialized")
    
    async def initialize(self) -> None:
        """Инициализация агента."""
        self.is_initialized = True
        logger.info("SpecToCodeAgent ready")
    
    async def generate(self, spec: Specification) -> GeneratedCode:
        """
        Генерация кода из спецификации.
        
        Args:
            spec: Спецификация
            
        Returns:
            Сгенерированный код
        """
        if not self.is_initialized:
            await self.initialize()
        
        logger.info(f"Generating {spec.language.value} code for {spec.name}")
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "type": "spec_to_code",
                "name": spec.name,
                "description": spec.description,
                "code_type": spec.code_type.value,
                "goal": f"generate {spec.language.value} {spec.code_type.value}",
                "constraints": spec.constraints or {},
                "requirements": spec.requirements,
            }
        )

        # Simple template-based generation (placeholder for LLM integration)
        code = self._generate_template(spec)
        
        return GeneratedCode(
            code=code,
            language=spec.language,
            code_type=spec.code_type,
            specification=spec,
            quality_score=0.85,
            metadata={
                "generated_by": "spec_to_code_agent",
                "thinking_techniques": list(
                    (self.last_thinking_context or {}).get("techniques", [])
                ),
            }
        )
    
    def _generate_template(self, spec: Specification) -> str:
        """Генерация шаблонного кода."""

        if spec.language == CodeLanguage.PYTHON:
            class_name = self._class_name(spec.name)
            requirements = self._python_literal(spec.requirements)
            description = self._python_literal(spec.description)
            name = self._python_literal(spec.name)
            code_type = self._python_literal(spec.code_type.value)
            return f'''# Generated: {spec.name}
# Type: {spec.code_type.value}
from datetime import datetime, timezone
from typing import Any


class {class_name}:
    """Auto-generated {spec.code_type.value}."""

    description = {description}
    requirements = {requirements}

    def __init__(self) -> None:
        self.name = {name}
        self.code_type = {code_type}
        self.created_at = datetime.now(timezone.utc)

    async def execute(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute {spec.name}."""
        return {{
            "status": "success",
            "name": self.name,
            "code_type": self.code_type,
            "requirements": list(self.requirements),
            "args": list(args),
            "kwargs": kwargs,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }}
'''

        if spec.language == CodeLanguage.JAVASCRIPT:
            return self._generate_javascript_template(spec, typed=False)

        if spec.language == CodeLanguage.TYPESCRIPT:
            return self._generate_javascript_template(spec, typed=True)

        if spec.language == CodeLanguage.GO:
            return self._generate_go_template(spec)

        if spec.language == CodeLanguage.RUST:
            return self._generate_rust_template(spec)

        if spec.language == CodeLanguage.JAVA:
            return self._generate_java_template(spec)

        raise ValueError(f"Unsupported language: {spec.language}")

    def _safe_identifier(self, value: str, *, default: str = "generated") -> str:
        identifier = re.sub(r"[^0-9a-zA-Z_]+", "_", value).strip("_").lower()
        if not identifier:
            identifier = default
        if identifier[0].isdigit():
            identifier = f"{default}_{identifier}"
        return identifier

    def _class_name(self, value: str) -> str:
        identifier = self._safe_identifier(value)
        class_name = "".join(part.capitalize() for part in identifier.split("_") if part)
        return class_name or "Generated"

    def _python_literal(self, value) -> str:
        return repr(value)

    def _json_literal(self, value) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _generate_javascript_template(self, spec: Specification, *, typed: bool) -> str:
        class_name = self._class_name(spec.name)
        name = self._json_literal(spec.name)
        code_type = self._json_literal(spec.code_type.value)
        description = self._json_literal(spec.description)
        requirements = self._json_literal(spec.requirements)

        if typed:
            return f'''// Generated: {spec.name}
// Type: {spec.code_type.value}
export type {class_name}Result = {{
  status: "success";
  name: string;
  codeType: string;
  requirements: string[];
  args: unknown[];
  executedAt: string;
}};

export class {class_name} {{
  readonly name = {name};
  readonly codeType = {code_type};
  readonly description = {description};
  readonly requirements = {requirements};

  async execute(...args: unknown[]): Promise<{class_name}Result> {{
    return {{
      status: "success",
      name: this.name,
      codeType: this.codeType,
      requirements: [...this.requirements],
      args,
      executedAt: new Date().toISOString(),
    }};
  }}
}}
'''

        return f'''// Generated: {spec.name}
// Type: {spec.code_type.value}
export class {class_name} {{
  constructor() {{
    this.name = {name};
    this.codeType = {code_type};
    this.description = {description};
    this.requirements = {requirements};
  }}

  async execute(...args) {{
    return {{
      status: "success",
      name: this.name,
      codeType: this.codeType,
      requirements: [...this.requirements],
      args,
      executedAt: new Date().toISOString(),
    }};
  }}
}}
'''

    def _generate_go_template(self, spec: Specification) -> str:
        class_name = self._class_name(spec.name)
        requirements = ", ".join(self._json_literal(req) for req in spec.requirements)
        return f'''// Generated: {spec.name}
// Type: {spec.code_type.value}
package generated

import "time"

type {class_name} struct {{
    Name string
    CodeType string
    Requirements []string
}}

func New{class_name}() {class_name} {{
    return {class_name}{{
        Name: {self._json_literal(spec.name)},
        CodeType: {self._json_literal(spec.code_type.value)},
        Requirements: []string{{{requirements}}},
    }}
}}

func (s {class_name}) Execute() map[string]any {{
    return map[string]any{{
        "status": "success",
        "name": s.Name,
        "code_type": s.CodeType,
        "requirements": s.Requirements,
        "executed_at": time.Now().UTC().Format(time.RFC3339),
    }}
}}
'''

    def _generate_rust_template(self, spec: Specification) -> str:
        class_name = self._class_name(spec.name)
        requirements = ", ".join(self._json_literal(req) for req in spec.requirements)
        return f'''// Generated: {spec.name}
// Type: {spec.code_type.value}
#[derive(Debug, Clone)]
pub struct {class_name} {{
    pub name: &'static str,
    pub code_type: &'static str,
    pub requirements: &'static [&'static str],
}}

impl {class_name} {{
    pub fn new() -> Self {{
        Self {{
            name: {self._json_literal(spec.name)},
            code_type: {self._json_literal(spec.code_type.value)},
            requirements: &[{requirements}],
        }}
    }}

    pub fn execute(&self) -> String {{
        format!("{{}}:{{}}:{{}}", self.name, self.code_type, self.requirements.len())
    }}
}}
'''

    def _generate_java_template(self, spec: Specification) -> str:
        class_name = self._class_name(spec.name)
        requirements = ", ".join(self._json_literal(req) for req in spec.requirements)
        return f'''// Generated: {spec.name}
// Type: {spec.code_type.value}
import java.time.Instant;
import java.util.List;
import java.util.Map;

public final class {class_name} {{
    private final String name = {self._json_literal(spec.name)};
    private final String codeType = {self._json_literal(spec.code_type.value)};
    private final List<String> requirements = List.of({requirements});

    public Map<String, Object> execute() {{
        return Map.of(
            "status", "success",
            "name", name,
            "codeType", codeType,
            "requirements", requirements,
            "executedAt", Instant.now().toString()
        );
    }}
}}
'''


# Singleton instance
_spec_to_code_agent: Optional[SpecToCodeAgent] = None


def get_spec_to_code_agent() -> SpecToCodeAgent:
    """Получение синглтона SpecToCodeAgent."""
    global _spec_to_code_agent
    if _spec_to_code_agent is None:
        _spec_to_code_agent = SpecToCodeAgent()
    return _spec_to_code_agent

