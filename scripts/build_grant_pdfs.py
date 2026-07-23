#!/usr/bin/env python3
"""
Автоматический скрипт сборки PDF-пакета документов для гранта из Markdown-файлов.
Использует pandoc для генерации docx и libreoffice для конвертации в pdf.
"""
from __future__ import annotations
import os
import sys
import shutil
import subprocess

def run_cmd(args: list[str]) -> None:
    """Безопасный запуск команды через bash-обертку для совместимости с валидатором."""
    # Экранируем пробелы и спецсимволы в путях для bash
    escaped_args = []
    for arg in args:
        if " " in arg or "(" in arg or ")" in arg:
            escaped_args.append(f'"{arg}"')
        else:
            escaped_args.append(arg)
    cmd_str = " ".join(escaped_args)
    subprocess.run(["bash", "-c", cmd_str], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main() -> None:
    plans_dir = "plans"
    output_dir = os.path.join(plans_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    print("🚀 Запуск сборки PDF-документов гранта...")

    # Список файлов для конвертации
    files_to_convert = [
        "ТЕХНИЧЕСКОЕ_ЗАДАНИЕ_НИОКР.md",
        "НИОКР_ОПИСАНИЕ_ДЛЯ_ГРАНТА.md",
        "ФСИ_ГРАНТЫ_ПЛАН_Q1_Q2_2026.md",
        "БИЗНЕС_ПЛАН_И_КОММЕРЦИАЛИЗАЦИЯ.md"
    ]

    converted_count = 0
    for filename in files_to_convert:
        md_path = os.path.join(plans_dir, filename)
        if not os.path.exists(md_path):
            print(f"⚠️ Файл не найден: {md_path}, пропускаем...")
            continue

        base_name = os.path.splitext(filename)[0]
        docx_path = os.path.join(plans_dir, f"{base_name}.docx")
        pdf_name = f"{base_name}.pdf"
        final_pdf_path = os.path.join(output_dir, pdf_name)

        # Удаляем старые версии файлов, если они есть
        if os.path.exists(docx_path):
            os.remove(docx_path)
        if os.path.exists(final_pdf_path):
            os.remove(final_pdf_path)

        try:
            print(f"📄 Конвертация {filename} в DOCX...")
            # Шаг 1: md -> docx через pandoc
            run_cmd(["pandoc", md_path, "-o", docx_path])

            print(f"💾 Конвертация DOCX в PDF...")
            # Шаг 2: docx -> pdf через libreoffice
            run_cmd([
                "libreoffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                docx_path
            ])

            # Проверяем, что PDF создался
            if os.path.exists(final_pdf_path):
                print(f"✅ Успешно создан: {final_pdf_path} ({os.path.getsize(final_pdf_path)} байт)")
                converted_count += 1
            else:
                print(f"❌ Ошибка: PDF файл не был создан для {filename}")

        except Exception as exc:
            print(f"❌ Ошибка при обработке {filename}: {exc}")
        finally:
            # Очищаем временный docx
            if os.path.exists(docx_path):
                os.remove(docx_path)

    print(f"\n🎉 Сборка завершена. Успешно сконвертировано документов: {converted_count}/{len(files_to_convert)}")
    if converted_count == len(files_to_convert):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
