from __future__ import annotations

import re


RU_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ы": "y",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "ь": "",
    "ъ": "",
}


def _transliterate(value: str) -> str:
    return "".join(RU_TO_LATIN.get(ch, ch) for ch in value)


def _normalize_part(value: str, fallback: str, max_len: int) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return fallback
    raw = raw.replace("@", "")
    raw = _transliterate(raw)
    raw = re.sub(r"\s+", "_", raw)
    raw = re.sub(r"[^\w.-]+", "_", raw, flags=re.UNICODE)
    raw = re.sub(r"_+", "_", raw).strip("._-")
    if not raw:
        return fallback
    return raw[:max_len]


PRESET_DEVICE_NAME_MAP = {
    "мой телефон": "my_phone",
    "мой компьютер": "my_computer",
    "домашний компьютер": "home_pc",
    "рабочий ноутбук": "work_laptop",
    "планшет": "tablet",
    "основное устройство": "main_device",
}


DEVICE_NAME_PATTERNS = (
    (r"^мой телефон\s+(\d+)$", "my_phone"),
    (r"^мой компьютер\s+(\d+)$", "my_computer"),
    (r"^домашний компьютер\s+(\d+)$", "home_pc"),
    (r"^рабочий ноутбук\s+(\d+)$", "work_laptop"),
    (r"^телефон реб[её]нка\s+(\d+)$", "child_phone"),
    (r"^телефон\s+(\d+)$", "phone"),
    (r"^компьютер\s+(\d+)$", "computer"),
    (r"^планшет\s+(\d+)$", "tablet"),
    (r"^устройство\s+(\d+)$", "device"),
)


def _translate_device_name(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return "device"
    if raw in PRESET_DEVICE_NAME_MAP:
        return PRESET_DEVICE_NAME_MAP[raw]

    for pattern, prefix in DEVICE_NAME_PATTERNS:
        match = re.match(pattern, raw)
        if match:
            return f"{prefix}_{match.group(1)}"

    return _normalize_part(raw, "device", 32)


def build_human_xray_email(
    user_id: int,
    username: str | None,
    device_name: str | None,
    user_uuid: str,
) -> str:
    username_part = _normalize_part(username or "", f"user{user_id}", 32)
    device_part = _translate_device_name(device_name)
    return f"{username_part}__{user_id}__{device_part}"
