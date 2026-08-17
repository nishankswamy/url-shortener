import pytest

from app import shortcode


def test_zero_encodes_to_first_char():
    assert shortcode.encode(0) == "0"


def test_roundtrip_is_lossless():
    for n in [1, 61, 62, 63, 3843, 100000, 999_999_999]:
        assert shortcode.decode(shortcode.encode(n)) == n


def test_base_boundary():
    assert shortcode.encode(61) == "Z"
    assert shortcode.encode(62) == "10"


def test_encoding_is_injective():
    codes = {shortcode.encode(n) for n in range(5000)}
    assert len(codes) == 5000


def test_negative_rejected():
    with pytest.raises(ValueError):
        shortcode.encode(-1)


def test_invalid_char_rejected():
    with pytest.raises(ValueError):
        shortcode.decode("abc!")
