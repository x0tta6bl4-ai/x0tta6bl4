#!/usr/bin/env python3
"""
Сканер баз данных на наличие секретов, PII и чувствительных данных
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

# Паттерны для поиска секретов
SECRET_PATTERNS = {
    "api_key": re.compile(
        r'(?i)(api[_-]?key|apikey)[\s]*[:=][\s]*["\']?([a-zA-Z0-9_-]{20,})["\']?'
    ),
    "password": re.compile(
        r'(?i)(password|passwd|pwd)[\s]*[:=][\s]*["\']?([^\s"\']{8,})["\']?'
    ),
    "token": re.compile(
        r'(?i)(token|bearer)[\s]*[:=][\s]*["\']?([a-zA-Z0-9_-]{20,})["\']?'
    ),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"),
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "ip_address": re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"),
}


def scan_database(db_path: Path) -> dict:
    """Сканировать базу данных на секреты"""
    findings = {"db_path": str(db_path), "secrets": [], "pii": [], "schema": {}}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получить список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        for table in tables:
            table_name = table[0]
            findings["schema"][table_name] = []

            # Получить схему таблицы
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            findings["schema"][table_name] = [col[1] for col in columns]

            # Сканировать содержимое
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1000;")
            rows = cursor.fetchall()

            for row in rows:
                for col_idx, value in enumerate(row):
                    if value is None:
                        continue

                    value_str = str(value)

                    # Поиск секретов
                    for secret_type, pattern in SECRET_PATTERNS.items():
                        matches = pattern.findall(value_str)
                        if matches:
                            findings["secrets"].append(
                                {
                                    "type": secret_type,
                                    "table": table_name,
                                    "column": columns[col_idx][1],
                                    "sample": (
                                        value_str[:100] + "..."
                                        if len(value_str) > 100
                                        else value_str
                                    ),
                                }
                            )

        conn.close()

    except Exception as e:
        findings["error"] = str(e)

    return findings


def main() -> None:
    """Главная функция сканирования"""
    db_dir = Path("~/.local/share/x0tta6bl4/databases/").expanduser()

    if not db_dir.exists():
        print(f"❌ Database directory not found: {db_dir}")
        return

    all_findings: list[dict] = []

    for db_file in db_dir.glob("*.db"):
        print(f"🔍 Scanning: {db_file.name}")
        findings = scan_database(db_file)

        if findings["secrets"]:
            print(f"⚠️  SECRETS FOUND: {len(findings['secrets'])} potential leaks")
        else:
            print(f"✅ No secrets detected")

        all_findings.append(findings)

    # Сохранить отчет
    report_path = Path("security_scan_report.json")
    with open(report_path, "w") as f:
        json.dump(all_findings, f, indent=2)

    print(f"\n📄 Full report saved: {report_path}")


if __name__ == "__main__":
    main()
