"""Xray client naming — stub for test compatibility."""


def build_human_xray_email(
    user_id: int,
    username: str,
    device_name: str,
    user_uuid: str = "",
) -> str:
    """Build a human-readable Xray email from transliterated username and device name."""
    import re

    def translit(text: str) -> str:
        mapping = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
            "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
            "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
            "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
            "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        }
        result = ""
        for ch in text.lower():
            result += mapping.get(ch, ch)
        return result

    clean_name = translit(username).replace(" ", "_")
    clean_device = re.sub(r"[^a-z0-9_]", "", translit(device_name.replace(" ", "_")))
    return f"{clean_name}__{user_id}__{clean_device}"
