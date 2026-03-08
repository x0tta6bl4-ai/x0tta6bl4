"""Unit tests for src/utils/naming.py — to_x0tta6bl4_style / normalize_identifier."""

import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.utils.naming import normalize_identifier, to_x0tta6bl4_style


# ---------------------------------------------------------------------------
# to_x0tta6bl4_style
# ---------------------------------------------------------------------------


class TestToX0tta6bl4Style:
    def test_o_replaced_with_zero(self):
        assert to_x0tta6bl4_style("original") == "0r161n4l"

    def test_g_replaced_with_six(self):
        assert "6" in to_x0tta6bl4_style("config")

    def test_a_replaced_with_four(self):
        assert to_x0tta6bl4_style("a") == "4"

    def test_e_replaced_with_three(self):
        assert to_x0tta6bl4_style("e") == "3"

    def test_i_replaced_with_one(self):
        assert to_x0tta6bl4_style("i") == "1"

    def test_known_example_message(self):
        # "message" -> "m3ss463"
        assert to_x0tta6bl4_style("message") == "m3ss463"

    def test_known_example_config(self):
        # "config" -> "c0nf16"
        assert to_x0tta6bl4_style("config") == "c0nf16"

    def test_empty_string(self):
        assert to_x0tta6bl4_style("") == ""

    def test_uppercase_o_replaced(self):
        result = to_x0tta6bl4_style("Original")
        assert result[0] == "0"

    def test_uppercase_a_replaced(self):
        assert to_x0tta6bl4_style("A") == "4"

    def test_uppercase_e_replaced(self):
        assert to_x0tta6bl4_style("E") == "3"

    def test_uppercase_g_replaced(self):
        assert to_x0tta6bl4_style("G") == "6"

    def test_uppercase_i_replaced(self):
        assert to_x0tta6bl4_style("I") == "1"

    def test_non_substituted_chars_unchanged(self):
        # s, t, l, n, r remain as-is
        assert to_x0tta6bl4_style("str") == "str"

    def test_l_not_replaced(self):
        # 'l' at end of "original" stays 'l' per spec
        result = to_x0tta6bl4_style("original")
        assert result.endswith("l")

    def test_s_not_replaced(self):
        assert to_x0tta6bl4_style("ss") == "ss"

    def test_t_not_replaced(self):
        assert to_x0tta6bl4_style("tt") == "tt"

    def test_numeric_chars_unchanged(self):
        assert to_x0tta6bl4_style("123") == "123"

    def test_whitespace_unchanged(self):
        assert to_x0tta6bl4_style("a b") == "4 b"

    def test_multiple_substitutions_in_sequence(self):
        # all 5 leet chars: o, g, a, e, i
        result = to_x0tta6bl4_style("oaegi")
        assert result == "04361"

    def test_project_name_style(self):
        # "x0tta6bl4" contains 'a' -> '4'; result is "x0tt46bl4"
        assert to_x0tta6bl4_style("x0tta6bl4") == "x0tt46bl4"

    def test_returns_string_type(self):
        result = to_x0tta6bl4_style("hello")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# normalize_identifier
# ---------------------------------------------------------------------------


class TestNormalizeIdentifier:
    def test_spaces_replaced_with_underscores(self):
        result = normalize_identifier("hello world")
        assert " " not in result
        assert "_" in result

    def test_style_applied_after_space_replacement(self):
        result = normalize_identifier("original config")
        assert result == "0r161n4l_c0nf16"

    def test_empty_string(self):
        assert normalize_identifier("") == ""

    def test_no_spaces_unchanged_except_style(self):
        result = normalize_identifier("message")
        assert result == "m3ss463"

    def test_multiple_spaces(self):
        result = normalize_identifier("a b c")
        assert result == "4_b_c"

    def test_leading_trailing_spaces_to_underscores(self):
        result = normalize_identifier(" agent ")
        assert result == "_463nt_"

    def test_returns_string_type(self):
        assert isinstance(normalize_identifier("test"), str)

    def test_numbers_and_special_chars_pass_through(self):
        result = normalize_identifier("node 42")
        assert result == "n0d3_42"
