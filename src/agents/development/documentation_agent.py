# 🤖 Documentation Agent - x0tta6bl4
"""
Documentation Agent - автоматическое обновление документации.
Генерирует и обновляет API документацию, runbooks и knowledge base.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DocType(Enum):
    """Тип документации."""
    API_REFERENCE = "api_reference"
    RUNBOOK = "runbook"
    README = "readme"
    CHANGELOG = "changelog"
    ARCHITECTURE = "architecture"
    GUIDE = "guide"


class DocFormat(Enum):
    """Формат документации."""
    MARKDOWN = "markdown"
    REST = "rest"
    HTML = "html"


@dataclass
class DocSpec:
    """Спецификация документации."""
    name: str
    doc_type: DocType
    title: str
    description: str
    source_files: list[str] = field(default_factory=list)
    output_path: str = "docs"
    format: DocFormat = DocFormat.MARKDOWN


@dataclass
class GeneratedDoc:
    """Сгенерированная документация."""
    spec: DocSpec
    content: str
    generated_at: datetime
    files: list[str] = field(default_factory=list)


class DocumentationAgent:
    """
    Documentation Agent для x0tta6bl4.
    
    Автоматически генерирует и обновляет документацию:
    - API reference из кода
    - Runbooks для операций
    - README файлы
    - Changelog
    - Architecture документы
    """
    
    def __init__(self, config: Optional[dict] = None):
        """
        Инициализация Documentation Agent.
        
        Args:
            config: Конфигурация агента
        """
        self.config = config or self._default_config()
        
        # Целевая директория для документации
        self.docs_root = Path(self.config.get("docs_root", "docs"))
        
        # История сгенерированных документов
        self.generated_docs: list[GeneratedDoc] = []
        
        logger.info("Documentation Agent initialized")
    
    def _default_config(self) -> dict:
        """Дефолтная конфигурация."""
        return {
            "docs_root": "docs",
            "auto_update": True,
            "include_examples": True,
            "include_api_docs": True,
            "source_paths": ["src/api", "src/services"],
        }
    
    async def generate_api_docs(self, source_path: str) -> GeneratedDoc:
        """
        Генерация API документации из исходного кода.
        
        Args:
            source_path: Путь к исходному коду
            
        Returns:
            Сгенерированная документация
        """
        logger.info(f"Generating API docs from {source_path}")
        
        # Парсинг исходного кода
        endpoints = await self._parse_endpoints(source_path)
        
        # Генерация документации
        content = self._generate_api_reference(endpoints)
        
        spec = DocSpec(
            name="api_reference",
            doc_type=DocType.API_REFERENCE,
            title="API Reference",
            description="Auto-generated API reference documentation",
            source_files=[source_path],
        )
        
        result = GeneratedDoc(
            spec=spec,
            content=content,
            generated_at=datetime.utcnow(),
            files=["api/reference.md"],
        )
        
        self.generated_docs.append(result)
        return result
    
    async def _parse_endpoints(self, source_path: str) -> list[dict]:
        """Парсинг endpoints из Python кода."""
        endpoints = []
        
        # Простой парсинг - ищем декораторы @router
        # В реальной реализации использовался бы AST
        
        try:
            from pathlib import Path
            path = Path(source_path)
            
            if path.is_file():
                files = [path]
            else:
                files = list(path.rglob("*.py"))
            
            for file in files:
                try:
                    content = file.read_text()
                    
                    # Поиск endpoint определений
                    patterns = [
                        r'@router\.(get|post|put|delete|patch)\(["\'](.+?)["\']',
                        r'@app\.(get|post|put|delete|patch)\(["\'](.+?)["\']',
                        r'def\s+(\w+)\s*\([^)]*\):\s*#\s*(.+)',
                    ]
                    
                    for pattern in patterns:
                        matches = re.finditer(pattern, content, re.MULTILINE)
                        for match in matches:
                            endpoints.append({
                                "method": match.group(1).upper() if match.lastindex >= 1 else "GET",
                                "path": match.group(2) if match.lastindex >= 2 else "/",
                                "source": str(file),
                            })
                            
                except Exception as e:
                    logger.debug(f"Error parsing {file}: {e}")
                    
        except Exception as e:
            logger.error(f"Error parsing endpoints: {e}")
        
        return endpoints
    
    def _generate_api_reference(self, endpoints: list[dict]) -> str:
        """Генерация API reference."""
        content = '''# API Reference

**Auto-generated documentation**

---

## Endpoints

| Method | Path | Source |
|--------|------|--------|
'''
        
        for ep in endpoints:
            method = ep.get("method", "GET")
            path = ep.get("path", "/")
            source = ep.get("source", "unknown")
            
            content += f"| `{method}` | `{path}` | `{source}` |\n"
        
        content += '''
---

## Usage

See individual endpoint documentation for details.

'''
        
        return content
    
    async def generate_runbook(self, title: str, steps: list[str]) -> GeneratedDoc:
        """
        Генерация runbook документации.
        
        Args:
            title: Название runbook
            steps: Шаги для выполнения
            
        Returns:
            Сгенерированная документация
        """
        content = f'''# {title}

**Generated:** {datetime.utcnow().isoformat()}

---

## Overview

This runbook provides step-by-step instructions for {title.lower()}.

## Prerequisites

- Access to production environment
- Required permissions
- Necessary tools installed

## Steps

'''
        
        for i, step in enumerate(steps, 1):
            content += f"### Step {i}: {step.get('title', 'Action')}\n\n"
            content += f"{step.get('description', '')}\n\n"
            
            if step.get('command'):
                content += "```bash\n"
                content += f"{step.get('command')}\n"
                content += "```\n\n"
            
            if step.get('expected_result'):
                content += f"**Expected Result:** {step['expected_result']}\n\n"
        
        content += '''
## Troubleshooting

If step fails:

1. Check logs for errors
2. Verify permissions
3. Contact on-call engineer

## Rollback

To rollback:
1. Stop current operation
2. Restore previous state
3. Verify system health
'''
        
        spec = DocSpec(
            name=title.lower().replace(" ", "_"),
            doc_type=DocType.RUNBOOK,
            title=title,
            description=f"Runbook for {title}",
        )
        
        result = GeneratedDoc(
            spec=spec,
            content=content,
            generated_at=datetime.utcnow(),
            files=[f"runbooks/{spec.name}.md"],
        )
        
        self.generated_docs.append(result)
        return result
    
    async def generate_readme(self, project_name: str, description: str) -> GeneratedDoc:
        """
        Генерация README файла.
        
        Args:
            project_name: Название проекта
            description: Описание проекта
            
        Returns:
            Сгенерированная документация
        """
        content = f'''# {project_name}

{description}

## Features

- Feature 1
- Feature 2
- Feature 3

## Installation

```bash
pip install {project_name.replace("-", "_")}
```

## Usage

```python
import {project_name.replace("-", "_")}

# Example usage
```

## API

See [API Reference](api/reference.md)

## Contributing

See [Contributing Guide](CONTRIBUTING.md)

## License

MIT

---

*Generated by Documentation Agent on {datetime.utcnow().isoformat()}*
'''
        
        spec = DocSpec(
            name="readme",
            doc_type=DocType.README,
            title="README",
            description=description,
        )
        
        result = GeneratedDoc(
            spec=spec,
            content=content,
            generated_at=datetime.utcnow(),
            files=["README.md"],
        )
        
        self.generated_docs.append(result)
        return result
    
    async def update_changelog(self, version: str, changes: dict) -> GeneratedDoc:
        """
        Обновление changelog.
        
        Args:
            version: Версия
            changes: Изменения (features, fixes, breaking)
            
        Returns:
            Сгенерированная документация
        """
        content = f'''# Changelog

All notable changes to this project will be documented in this file.

## [{version}] - {datetime.utcnow().strftime("%Y-%m-%d")}

### Added
'''
        
        for change in changes.get("added", []):
            content += f"- {change}\n"
        
        content += "\n### Changed\n"
        for change in changes.get("changed", []):
            content += f"- {change}\n"
        
        content += "\n### Fixed\n"
        for change in changes.get("fixed", []):
            content += f"- {change}\n"
        
        if changes.get("breaking"):
            content += "\n### Breaking Changes\n"
            for change in changes["breaking"]:
                content += f"- {change}\n"
        
        content += "\n---\n"
        
        # Чтение существующего changelog
        changelog_path = self.docs_root / "CHANGELOG.md"
        if changelog_path.exists():
            existing = changelog_path.read_text()
            content = existing + "\n\n" + content
        
        spec = DocSpec(
            name="changelog",
            doc_type=DocType.CHANGELOG,
            title="Changelog",
            description=f"Changes for version {version}",
        )
        
        result = GeneratedDoc(
            spec=spec,
            content=content,
            generated_at=datetime.utcnow(),
            files=["CHANGELOG.md"],
        )
        
        self.generated_docs.append(result)
        return result
    
    async def save_docs(self, doc: GeneratedDoc, base_path: str = None) -> list[str]:
        """
        Сохранение документации в файлы.
        
        Args:
            doc: Сгенерированная документация
            base_path: Базовый путь для сохранения
            
        Returns:
            Список сохранённых файлов
        """
        base_path = base_path or str(self.docs_root)
        saved_files = []
        
        for filename in doc.files:
            filepath = Path(base_path) / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            filepath.write_text(doc.content)
            saved_files.append(str(filepath))
            logger.info(f"Saved documentation to {filepath}")
        
        return saved_files
    
    def get_generated_docs(self) -> list[GeneratedDoc]:
        """Получение истории сгенерированной документации."""
        return self.generated_docs
    
    async def scan_and_update(self) -> list[GeneratedDoc]:
        """
        Сканирование исходного кода и обновление документации.
        
        Returns:
            Список обновлённых документов
        """
        updated = []
        
        # Сканирование API endpoints
        for source_path in self.config.get("source_paths", []):
            try:
                doc = await self.generate_api_docs(source_path)
                await self.save_docs(doc)
                updated.append(doc)
            except Exception as e:
                logger.error(f"Error scanning {source_path}: {e}")
        
        return updated


# Синглтон экземпляр
_documentation_agent_instance: Optional[DocumentationAgent] = None


def get_documentation_agent() -> DocumentationAgent:
    """Получение синглтона Documentation Agent."""
    global _documentation_agent_instance
    if _documentation_agent_instance is None:
        _documentation_agent_instance = DocumentationAgent()
    return _documentation_agent_instance
