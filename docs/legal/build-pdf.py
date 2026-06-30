#!/usr/bin/env python3
"""Сборка пакета юридических документов для распечатки."""

import os
from weasyprint import HTML

DOCS_DIR = "/mnt/projects/docs/legal"
OUTPUT = "/mnt/projects/docs/legal/package-for-printing.pdf"

FILES = [
    "application-to-fts.md",
    "objection-to-court-order.md", 
    "application-to-bailiffs.md",
]

def md_to_html(filepath):
    import markdown
    with open(filepath) as f:
        md = f.read()
    html_body = markdown.markdown(md, extensions=['extra'])
    title = os.path.splitext(os.path.basename(filepath))[0]
    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<style>
@page {{ size: A4; margin: 2cm; }}
body {{ font-family: 'Liberation Serif', 'Times New Roman', serif; font-size: 12pt; line-height: 1.5; }}
h1 {{ font-size: 16pt; text-align: center; }}
h2 {{ font-size: 14pt; }}
strong {{ font-weight: bold; }}
hr {{ margin: 2em 0; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""
    return html

parts = []
for f in FILES:
    if os.path.exists(os.path.join(DOCS_DIR, f)):
        parts.append(md_to_html(os.path.join(DOCS_DIR, f)))

full_html = "<hr style='page-break-after: always;'>".join(parts)
HTML(string=full_html).write_pdf(OUTPUT)

print(f"PDF создан: {OUTPUT}")
size = os.path.getsize(OUTPUT)
print(f"Размер: {size} байт")
