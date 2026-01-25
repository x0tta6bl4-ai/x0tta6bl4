#!/usr/bin/env python3
"""
Скрипт для поиска email адресов контактов
Использование: python3 scripts/find_email_addresses.py
"""

import re
import json
from pathlib import Path

# Компании из EMAIL_CONTACTS_LIST.md
COMPANIES = [
    {"name": "Сбербанк", "contact": "VP Security / Risk Officer"},
    {"name": "ВТБ", "contact": "CISO / InfoSec Lead"},
    {"name": "Альфа-Банк", "contact": "Platform/Infrastructure Lead"},
    {"name": "Тинькофф", "contact": "DevOps Director"},
    {"name": "Yandex", "contact": "VP Infrastructure / Chief Architect"},
    {"name": "VK", "contact": "Platform Engineer / SRE Lead"},
    {"name": "Avito", "contact": "Principal Engineer (Platform)"},
    {"name": "Ozon", "contact": "Infrastructure/Platform Lead"},
    {"name": "Kaspersky", "contact": "Security Lead"},
]

def generate_email_patterns(company_name, contact_title):
    """Генерирует возможные email паттерны"""
    patterns = []
    
    # Варианты доменов
    domains = [
        f"{company_name.lower().replace(' ', '')}.ru",
        f"{company_name.lower().replace(' ', '')}.com",
        f"mail.{company_name.lower().replace(' ', '')}.ru",
    ]
    
    # Варианты имен (нужно будет заполнить вручную)
    name_variants = ["[first].[last]", "[first]_[last]", "[first][last]"]
    
    # Варианты должностей в email
    title_variants = {
        "VP Security": ["security", "infosec", "ciso"],
        "CISO": ["ciso", "security", "infosec"],
        "DevOps Director": ["devops", "platform", "infrastructure"],
        "VP Infrastructure": ["infrastructure", "platform", "engineering"],
        "Platform Engineer": ["platform", "sre", "engineering"],
        "Principal Engineer": ["engineering", "platform", "principal"],
    }
    
    return {
        "company": company_name,
        "contact": contact_title,
        "suggested_domains": domains,
        "email_patterns": [
            f"{{first}}.{{last}}@{domain}" for domain in domains
        ],
        "linkedin_search": f"{company_name} {contact_title}",
        "google_search": f'"{company_name}" "{contact_title}" email',
    }

def create_email_finder_guide():
    """Создает guide для поиска email адресов"""
    
    output = []
    output.append("# 📧 Email Finder Guide\n")
    output.append("**Цель**: Найти email адреса для контактов из EMAIL_CONTACTS_LIST.md\n\n")
    output.append("---\n\n")
    
    for company in COMPANIES:
        patterns = generate_email_patterns(company["name"], company["contact"])
        
        output.append(f"## {company['name']}\n\n")
        output.append(f"**Контакт**: {company['contact']}\n\n")
        output.append("### Способы поиска:\n\n")
        output.append("1. **LinkedIn**:\n")
        output.append(f"   - Поиск: {patterns['linkedin_search']}\n")
        output.append("   - Проверьте профиль на наличие email\n")
        output.append("   - Используйте LinkedIn Sales Navigator (если есть)\n\n")
        
        output.append("2. **Google Search**:\n")
        output.append(f"   - Запрос: {patterns['google_search']}\n")
        output.append("   - Проверьте результаты на наличие email\n\n")
        
        output.append("3. **Сайт компании**:\n")
        output.append(f"   - Откройте {company['name']}.ru или .com\n")
        output.append("   - Раздел 'Контакты' или 'Команда'\n")
        output.append("   - Или используйте общий формат: contact@[domain]\n\n")
        
        output.append("4. **Возможные домены**:\n")
        for domain in patterns['suggested_domains']:
            output.append(f"   - {domain}\n")
        output.append("\n")
        
        output.append("5. **Email Hunter / Hunter.io**:\n")
        output.append(f"   - Поиск по домену: {patterns['suggested_domains'][0]}\n")
        output.append("   - Фильтр по должности\n\n")
        
        output.append("---\n\n")
    
    output.append("## ✅ После нахождения email\n\n")
    output.append("1. Добавьте в EMAIL_CONTACTS_LIST.md\n")
    output.append("2. Проверьте email через email verification tool\n")
    output.append("3. Используйте в prepare_emails.py\n\n")
    
    return "".join(output)

if __name__ == "__main__":
    guide = create_email_finder_guide()
    
    output_file = Path("EMAIL_FINDER_GUIDE.md")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(guide)
    
    print("✅ EMAIL_FINDER_GUIDE.md создан!")
    print("\n📋 Используйте этот guide для поиска email адресов")

