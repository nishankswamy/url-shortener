"""Short code generation.

Codes are derived from the row's auto-increment id, never from random bytes.
That makes collisions impossible by construction — no retry loop, no uniqueness
check on the hot path.

The naive version (`encode(id)`) is enumerable: given `q0W`, anyone can walk
your entire link table. The fix is not randomness — that reintroduces
collisions — but a *bijection* over the code space. Multiply the id by a
constant coprime with the modulus and the mapping stays one-to-one while the
output stops looking sequential:

    1 -> Nk9pTx    2 -> 1V8Fnv    3 -> 2CxWHt

Both modes are kept so the tradeoff stays visible. See SHORTCODE_MODE.
"""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)
_INDEX = {char: i for i, char in enumerate(ALPHABET)}

# Six base62 characters ≈ 56.8 billion codes. Enough that you will never
# exhaust it, small enough that the codes stay short.
CODE_LENGTH = 6
MODULUS = BASE**CODE_LENGTH

# Any constant coprime with MODULUS gives a bijection. MODULUS factors as
# 2^6 * 31^6, so an odd prime that isn't 31 qualifies. This one is prime.
MULTIPLIER = 1_580_030_173
_INVERSE = pow(MULTIPLIER, -1, MODULUS)


def encode(number: int) -> str:
    """Encode a non-negative integer as a base62 string."""
    if number < 0:
        raise ValueError("cannot encode a negative number")
    if number == 0:
        return ALPHABET[0]

    digits = []
    while number > 0:
        number, remainder = divmod(number, BASE)
        digits.append(ALPHABET[remainder])
    return "".join(reversed(digits))


def decode(code: str) -> int:
    """Decode a base62 string back to an integer."""
    number = 0
    for char in code:
        if char not in _INDEX:
            raise ValueError(f"invalid base62 character: {char!r}")
        number = number * BASE + _INDEX[char]
    return number


def obfuscate(number: int) -> str:
    """Map an id to a fixed-length code that doesn't reveal its position.

    Still bijective, so still collision-free. Note this is obfuscation, not
    encryption — the multiplier is in the source. It stops casual enumeration,
    it does not make a link secret. Anything that needs to stay private needs
    real authorisation on the redirect.
    """
    if not 0 <= number < MODULUS:
        raise ValueError(f"id {number} outside the {CODE_LENGTH}-character code space")
    return encode(number * MULTIPLIER % MODULUS).rjust(CODE_LENGTH, ALPHABET[0])


def deobfuscate(code: str) -> int:
    """Recover the id from an obfuscated code."""
    return decode(code) * _INVERSE % MODULUS
