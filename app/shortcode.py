"""Base62 encoding.

Codes are derived from the row's auto-increment id rather than random bytes,
which means collisions are impossible by construction — no retry loop, no
uniqueness check on the hot path.

The trade-off: codes are sequential, so anyone can enumerate your links.
Fine for a demo, not for anything private. See the note at the bottom for
the fix if you want unguessable codes.
"""

ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE = len(ALPHABET)
_INDEX = {char: i for i, char in enumerate(ALPHABET)}


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


# Stretch goal: make codes unguessable.
#
# Multiply the id by a large odd number coprime with 62**n and mask it
# (a Feistel network or simple multiplicative inverse over the id space).
# You keep collision-freedom because the mapping stays bijective, but the
# output no longer looks sequential. Implement `obfuscate(id)` /
# `deobfuscate(code)` here and the rest of the app doesn't change.
