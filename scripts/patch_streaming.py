#!/usr/bin/env python3
"""Патч стриминга Hermes gateway.

Проблема: "stream": True жёстко зашит в теле запроса к LLM провайдеру.
На OpenRouter/Anthropic длинные ответы обрываются из-за балансировщика.

Фикс: добавляет чтение HERMES_MODEL_STREAM (True/False) из конфига.
По умолчанию True (обратная совместимость).

Использование:
  export HERMES_MODEL_STREAM=false   # отключить стриминг к модели
  python3 patch_streaming.py         # применить патч
  python3 patch_streaming.py --revert  # откатить
"""

import os
import sys

# Файлы для патча
FILES = {
    "agent": (
        "/home/x0ttta6bl4/.hermes/hermes-agent/agent/chat_completion_helpers.py",
        '"stream": True,',
        '"stream": os.environ.get("HERMES_MODEL_STREAM", "true").lower() == "true",',
    ),
    "gateway": (
        "/home/x0ttta6bl4/.hermes/hermes-agent/gateway/run.py",
        '"stream": True,',
        '"stream": os.environ.get("HERMES_MODEL_STREAM", "true").lower() == "true",',
    ),
}


def patch_file(filepath, old_text, new_text, revert=False):
    """Patch or revert a single file."""
    if not os.path.exists(filepath):
        print(f"  ❌ Not found: {filepath}")
        return False

    with open(filepath) as f:
        content = f.read()

    target = old_text if not revert else new_text
    replacement = new_text if not revert else old_text

    if target not in content:
        print(f"  ⚠️  Pattern not found in {os.path.basename(filepath)}")
        if revert:
            print(f"     (already reverted?)")
        else:
            print(f"     (already patched?)")
        return False

    if content.count(target) > 1:
        print(f"  ⚠️  Multiple matches ({content.count(target)}x) in {os.path.basename(filepath)}")
        return False

    new_content = content.replace(target, replacement)
    with open(filepath, "w") as f:
        f.write(new_content)
    print(f"  ✅ Patched: {os.path.basename(filepath)}")
    return True


def verify_patch(filepath, old_text, revert=False):
    """Verify a file is in expected state."""
    if not os.path.exists(filepath):
        return False
    with open(filepath) as f:
        content = f.read()
    return old_text not in content if not revert else old_text in content


def main():
    revert = "--revert" in sys.argv

    if revert:
        print("🔧 Откат патча стриминга...")
    else:
        print("🔧 Патч стриминга Hermes...")
        print()
        print("  После патча стриминг к модели можно отключить:")
        print("  export HERMES_MODEL_STREAM=false")
        print("  По умолчанию: true (стриминг включён)")
        print()

    success = 0
    failed = 0
    for key, (filepath, old_text, new_text) in FILES.items():
        if patch_file(filepath, old_text, new_text, revert=revert):
            success += 1
        else:
            failed += 1

    print()
    if revert:
        print(f"📊 Откачено: {success}, ошибок: {failed}")
    else:
        print(f"📊 Запатчено: {success}, ошибок: {failed}")
        print()
        print("💡 Теперь для отключения стриминга:")
        print('   export HERMES_MODEL_STREAM="false"')
        print("   # и перезапустить Hermes gateway")
        print()
        print("💡 Для отката:")
        print("   python3 patch_streaming.py --revert")


if __name__ == "__main__":
    main()
