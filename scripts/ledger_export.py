#!/usr/bin/env python3
"""
Экспорт Continuity Ledger в различные форматы

Поддерживаемые форматы:
- JSON
- HTML
- Markdown (с форматированием)
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CONTINUITY_FILE = PROJECT_ROOT / "CONTINUITY.md"


def export_json(output_file: Path):
    """Экспорт ledger в JSON"""
    if not CONTINUITY_FILE.exists():
        print(f"❌ Файл не найден: {CONTINUITY_FILE}")
        sys.exit(1)

    content = CONTINUITY_FILE.read_text(encoding="utf-8")

    # Парсинг разделов
    sections = []
    current_section = None
    current_content = []

    for line in content.splitlines():
        if line.startswith("## "):
            if current_section:
                sections.append(
                    {"title": current_section, "content": "\n".join(current_content)}
                )
            current_section = line.replace("## ", "").strip()
            current_content = [line]
        else:
            current_content.append(line)

    if current_section:
        sections.append(
            {"title": current_section, "content": "\n".join(current_content)}
        )

    data = {
        "metadata": {
            "source": str(CONTINUITY_FILE),
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "total_sections": len(sections),
            "file_size": CONTINUITY_FILE.stat().st_size,
        },
        "sections": sections,
    }

    output_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"✅ Экспортировано в JSON: {output_file}")


def export_html(output_file: Path):
    """Экспорт ledger в HTML"""
    if not CONTINUITY_FILE.exists():
        print(f"❌ Файл не найден: {CONTINUITY_FILE}")
        sys.exit(1)

    content = CONTINUITY_FILE.read_text(encoding="utf-8")

    # Простое преобразование markdown в HTML
    html_content = content

    # Заголовки
    html_content = re.sub(
        r"^## (.+)$", r"<h2>\1</h2>", html_content, flags=re.MULTILINE
    )
    html_content = re.sub(
        r"^### (.+)$", r"<h3>\1</h3>", html_content, flags=re.MULTILINE
    )
    html_content = re.sub(
        r"^#### (.+)$", r"<h4>\1</h4>", html_content, flags=re.MULTILINE
    )

    # Ссылки
    html_content = re.sub(
        r"\[([^\]]+)\]\(([^\)]+)\)", r'<a href="\2">\1</a>', html_content
    )

    # Код блоки
    html_content = re.sub(
        r"```(\w+)?\n([\s\S]*?)```", r"<pre><code>\2</code></pre>", html_content
    )

    # Inline код
    html_content = re.sub(r"`([^`]+)`", r"<code>\1</code>", html_content)

    # Списки
    html_content = re.sub(r"^- (.+)$", r"<li>\1</li>", html_content, flags=re.MULTILINE)
    html_content = re.sub(
        r"^(\d+)\. (.+)$", r"<li>\2</li>", html_content, flags=re.MULTILINE
    )

    # Параграфы
    paragraphs = html_content.split("\n\n")
    html_content = "\n".join(
        [
            f"<p>{p}</p>" if p.strip() and not p.startswith("<") else p
            for p in paragraphs
        ]
    )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Continuity Ledger</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }}
        h2 {{
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        h3 {{
            color: #34495e;
            margin-top: 30px;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
        }}
        a {{
            color: #3498db;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <h1>Continuity Ledger</h1>
    <p><em>Экспортировано: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</em></p>
    {html_content}
</body>
</html>"""

    output_file.write_text(html, encoding="utf-8")
    print(f"✅ Экспортировано в HTML: {output_file}")


def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Экспорт Continuity Ledger в различные форматы"
    )
    parser.add_argument("format", choices=["json", "html"], help="Формат экспорта")
    parser.add_argument("-o", "--output", type=Path, help="Выходной файл")

    args = parser.parse_args()

    if args.output:
        output_file = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = PROJECT_ROOT / f"CONTINUITY_export_{timestamp}.{args.format}"

    if args.format == "json":
        export_json(output_file)
    elif args.format == "html":
        export_html(output_file)


if __name__ == "__main__":
    main()
