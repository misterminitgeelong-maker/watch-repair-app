"""JSON trailing-comma repair must not touch string contents."""

from parser import _strip_trailing_commas


def test_strips_trailing_comma_before_brace():
    assert _strip_trailing_commas('{"a": 1,}') == '{"a": 1}'
    assert _strip_trailing_commas('{"a": 1, "b": [2,]}') == '{"a": 1, "b": [2]}'


def test_preserves_comma_inside_strings():
    raw = '{"title": "foo, } bar", "n": 1,}'
    assert _strip_trailing_commas(raw) == '{"title": "foo, } bar", "n": 1}'


def test_preserves_escaped_quotes():
    raw = '{"title": "say \\"hi, }\\"",}'
    assert _strip_trailing_commas(raw) == '{"title": "say \\"hi, }\\""}'
