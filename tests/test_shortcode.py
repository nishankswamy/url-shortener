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


# --- obfuscated mode -------------------------------------------------------


def test_obfuscation_roundtrips():
    for n in [0, 1, 2, 999, 123_456, 50_000_000]:
        assert shortcode.deobfuscate(shortcode.obfuscate(n)) == n


def test_obfuscation_is_collision_free():
    """The whole point of a bijection — no two ids share a code."""
    codes = {shortcode.obfuscate(n) for n in range(20_000)}
    assert len(codes) == 20_000


def test_obfuscated_codes_are_fixed_length():
    assert all(len(shortcode.obfuscate(n)) == shortcode.CODE_LENGTH for n in range(500))


def test_consecutive_ids_look_unrelated():
    """Sequential ids must not produce codes with a shared prefix, or the
    scheme has not actually stopped enumeration."""
    a, b, c = (shortcode.obfuscate(n) for n in (1000, 1001, 1002))
    assert a[:3] != b[:3] != c[:3]


def test_multiplier_is_invertible():
    assert shortcode.MULTIPLIER * shortcode._INVERSE % shortcode.MODULUS == 1


def test_id_beyond_code_space_rejected():
    with pytest.raises(ValueError):
        shortcode.obfuscate(shortcode.MODULUS)
