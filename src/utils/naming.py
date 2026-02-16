def to_x0tta6bl4_style(text: str) -> str:
    """
    Applies the x0tta6bl4 selective coding style:
    - 'o' -> '0'
    - 'g' -> '6'
    - 'a' -> '4'

    Examples:
    - original -> 0r161n4l
    - message -> m3ss463 (Note: 'e' -> '3' is common in leet but user spec only listed o,g,a explicitly in one list,
      but example shows m3ss463 so 'e'->'3' is implied by example)

    Wait, looking at user spec examples:
    - message -> m3ss463 (implies e->3)
    - config -> c0nf16 (implies i->1 maybe? No, i is 1 in standard leet, but let's check user spec carefully)

    User spec says:
    - 'o' -> '0'
    - 'g' -> '6'
    - 'a' -> '4'
    - "Другие буквы остаются без изменений" (Other letters remain unchanged)

    BUT Examples show:
    - original -> 0r161n4l (i -> 1)
    - message -> m3ss463 (e -> 3)
    - config -> c0nf16 (i -> 1)

    So the explicit list was incomplete. I should follow the examples as they represent the ground truth of the style.
    Common leet substitutions observed in examples:
    o -> 0
    g -> 6
    a -> 4
    e -> 3
    i -> 1
    """
    chars = list(text)
    result = []
    for char in chars:
        lower_char = char.lower()
        if lower_char == "o":
            result.append("0")
        elif lower_char == "g":
            result.append("6")
        elif lower_char == "a":
            result.append("4")
        elif lower_char == "e":
            result.append("3")
        elif lower_char == "i":
            result.append("1")
        elif (
            lower_char == "l" and char.islower()
        ):  # Avoid confusing L with 1 if possible, but standard leet l->1 often.
            # In "original" -> "0r161n4l", the 'l' at the end remains 'l'.
            # So 'l' is NOT changed.
            result.append(char)
        elif lower_char == "s":
            # "message" -> "m3ss463" - s remains s.
            result.append(char)
        elif lower_char == "t":
            # "x0tta6bl4" - t remains t.
            result.append(char)
        else:
            result.append(char)

    return "".join(result)


def normalize_identifier(text: str) -> str:
    """
    Normalizes a string to be used as an ID, applying the style.
    """
    return to_x0tta6bl4_style(text.replace(" ", "_"))
