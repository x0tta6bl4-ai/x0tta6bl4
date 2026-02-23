#!/usr/bin/env python3
"""
Валидатор скиллов Claude.
Проверяет соответствие скилла требованиям документации Anthropic.
"""

import os
import sys
import re
import yaml
from pathlib import Path


class SkillValidator:
    def __init__(self, skill_path: str):
        self.skill_path = Path(skill_path)
        self.errors = []
        self.warnings = []
        
    def validate(self) -> bool:
        """Запустить все проверки. Возвращает True если скилл валиден."""
        self._check_structure()
        self._check_skill_md()
        self._check_naming()
        self._check_no_forbidden_files()
        
        return len(self.errors) == 0
    
    def _check_structure(self):
        """Проверить структуру папки."""
        if not self.skill_path.exists():
            self.errors.append(f"Папка скилла не найдена: {self.skill_path}")
            return
            
        skill_md = self.skill_path / "SKILL.md"
        if not skill_md.exists():
            # Проверить вариации
            variations = ["skill.md", "Skill.md", "SKILL.MD"]
            found = None
            for var in variations:
                if (self.skill_path / var).exists():
                    found = var
                    break
            if found:
                self.errors.append(f"Найден '{found}', но должен быть точно 'SKILL.md' (case-sensitive)")
            else:
                self.errors.append("SKILL.md не найден в папке скилла")
    
    def _check_skill_md(self):
        """Проверить содержимое SKILL.md."""
        skill_md = self.skill_path / "SKILL.md"
        if not skill_md.exists():
            return
            
        content = skill_md.read_text(encoding='utf-8')
        
        # Проверить frontmatter
        if not content.startswith('---'):
            self.errors.append("SKILL.md должен начинаться с YAML frontmatter (---)")
            return
            
        # Извлечь frontmatter
        parts = content.split('---', 2)
        if len(parts) < 3:
            self.errors.append("YAML frontmatter не закрыт (нужен второй ---)")
            return
            
        frontmatter_text = parts[1].strip()
        body = parts[2].strip()
        
        # Парсить YAML
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            self.errors.append(f"Ошибка парсинга YAML frontmatter: {e}")
            return
            
        if not isinstance(frontmatter, dict):
            self.errors.append("Frontmatter должен быть YAML dictionary")
            return
        
        # Проверить обязательные поля
        if 'name' not in frontmatter:
            self.errors.append("Отсутствует обязательное поле 'name' в frontmatter")
        else:
            self._validate_name(frontmatter['name'])
            
        if 'description' not in frontmatter:
            self.errors.append("Отсутствует обязательное поле 'description' в frontmatter")
        else:
            self._validate_description(frontmatter['description'])
        
        # Проверить XML теги
        if '<' in frontmatter_text or '>' in frontmatter_text:
            self.errors.append("XML теги (< >) запрещены в frontmatter")
        
        # Проверить длину body
        lines = body.split('\n')
        if len(lines) > 500:
            self.warnings.append(f"SKILL.md body содержит {len(lines)} строк (рекомендуется < 500)")
        
        words = len(body.split())
        if words > 5000:
            self.warnings.append(f"SKILL.md body содержит {words} слов (рекомендуется < 5000)")
    
    def _validate_name(self, name: str):
        """Проверить имя скилла."""
        if not name:
            self.errors.append("Поле 'name' пустое")
            return
            
        # Только kebab-case
        if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
            self.errors.append(f"Имя '{name}' должно быть в kebab-case (только строчные, цифры, дефисы)")
        
        # Запрещённые слова
        if 'claude' in name.lower():
            self.errors.append("Слово 'claude' запрещено в имени скилла")
        if 'anthropic' in name.lower():
            self.errors.append("Слово 'anthropic' запрещено в имени скилла")
        
        # Имя должно совпадать с папкой
        if name != self.skill_path.name:
            self.warnings.append(f"Имя '{name}' не совпадает с именем папки '{self.skill_path.name}'")
    
    def _validate_description(self, description: str):
        """Проверить description."""
        if not description:
            self.errors.append("Поле 'description' пустое")
            return
            
        if len(description) > 1024:
            self.errors.append(f"Description слишком длинный ({len(description)} символов, максимум 1024)")
        
        # Проверить наличие триггеров
        trigger_keywords = ['use when', 'when user', 'trigger', 'ask', 'mention', 'request']
        has_trigger = any(kw in description.lower() for kw in trigger_keywords)
        if not has_trigger:
            self.warnings.append("Description не содержит явных триггеров (рекомендуется 'Use when...')")
        
        # Проверить от первого лица
        first_person = ['i can', 'i will', 'i help', 'you can use this']
        for fp in first_person:
            if fp in description.lower():
                self.warnings.append(f"Description содержит '{fp}' - рекомендуется третье лицо")
    
    def _check_naming(self):
        """Проверить naming conventions для папки."""
        folder_name = self.skill_path.name
        
        if ' ' in folder_name:
            self.errors.append(f"Имя папки '{folder_name}' содержит пробелы (используйте kebab-case)")
        
        if '_' in folder_name:
            self.errors.append(f"Имя папки '{folder_name}' содержит подчёркивания (используйте kebab-case)")
        
        if folder_name != folder_name.lower():
            self.errors.append(f"Имя папки '{folder_name}' содержит заглавные буквы (используйте kebab-case)")
    
    def _check_no_forbidden_files(self):
        """Проверить отсутствие запрещённых файлов."""
        forbidden = ['README.md', 'INSTALLATION_GUIDE.md', 'QUICK_REFERENCE.md', 'CHANGELOG.md']
        
        for fname in forbidden:
            if (self.skill_path / fname).exists():
                self.errors.append(f"Файл '{fname}' не должен быть в папке скилла")
    
    def print_report(self):
        """Вывести отчёт валидации."""
        print(f"\n{'='*60}")
        print(f"Валидация скилла: {self.skill_path}")
        print(f"{'='*60}\n")
        
        if self.errors:
            print("❌ ОШИБКИ:")
            for err in self.errors:
                print(f"   • {err}")
            print()
        
        if self.warnings:
            print("⚠️  ПРЕДУПРЕЖДЕНИЯ:")
            for warn in self.warnings:
                print(f"   • {warn}")
            print()
        
        if not self.errors and not self.warnings:
            print("✅ Скилл прошёл все проверки!")
        elif not self.errors:
            print("✅ Критических ошибок нет, но есть предупреждения.")
        else:
            print("❌ Скилл не прошёл валидацию. Исправьте ошибки.")
        
        print()
        return len(self.errors) == 0


def main():
    if len(sys.argv) < 2:
        print("Использование: python validate_skill.py <путь_к_папке_скилла>")
        print("Пример: python validate_skill.py ./my-skill")
        sys.exit(1)
    
    skill_path = sys.argv[1]
    validator = SkillValidator(skill_path)
    is_valid = validator.validate()
    validator.print_report()
    
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
