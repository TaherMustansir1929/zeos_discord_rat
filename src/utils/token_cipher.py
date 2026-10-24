"""Encrypt the token of the bot so the executable carries no readable one.

The plain token of a Discord bot is a secret, a readable copy inside the
executable would hand it to anyone who opens the file in an editor or who
searches the binary for the known shape of a bot token.

The token is shipped as one encoded line of letters and numbers:

    encrypted = header + seed + (checksum + token) XOR keystream(seed)

The `seed` of the keystream is stored inside the same line, but it is a
random value of every encryption and it does not carry the token itself.
The checksum lets the startup detect a damaged or shortened line instead
of handing Discord a broken token.
"""

import base64
import hashlib
import secrets

# The first byte shows the version of the line, the rest marks the format.
# A wrong header is declined before any data is read.
HEADER = bytes([1]) + b"BTOK"

# The length of the random seed of the keystream.
SEED_LENGTH = 32

# The length of the checksum that protects the token.
CHECK_LENGTH = 8


def _keystream(seed: bytes, length: int) -> bytes:
    """Build a long stream of pseudorandom bytes out of the seed."""
    blocks: list[bytes] = []

    for counter in range(0, -(-length // hashlib.sha256().digest_size)):
        blocks.append(hashlib.sha256(seed + counter.to_bytes(4, "big")).digest())

    return b"".join(blocks)[:length]


def _xor(data: bytes, stream: bytes) -> bytes:
    """Mix two equally long blocks of bytes into one."""
    return bytes(
        byte ^ mask for byte, mask in zip(data, stream, strict=True)
    )


def encrypt_token(token: str) -> str:
    """Turn a plain bot token into the encoded line for the source file.

    Every call produces a different line because the seed is random.
    """
    data = token.encode("utf-8")

    if not data:
        raise ValueError("The token is empty.")

    payload = hashlib.sha256(data).digest()[:CHECK_LENGTH] + data
    seed = secrets.token_bytes(SEED_LENGTH)
    mixed = HEADER + seed + _xor(payload, _keystream(seed, len(payload)))

    return base64.b85encode(mixed).decode("ascii")


def decrypt_token(line: str) -> str:
    """Rebuild the plain bot token out of the encoded line.

    The line has to come from the encrypter that belongs to this module.
    A shortened or edited line raises a `ValueError` with a message that
    names the problem instead of a broken token.
    """
    try:
        raw = base64.b85decode(line.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise ValueError("The token line is not a valid encoding.") from None

    header_length = len(HEADER)

    if raw[:header_length] != HEADER or len(raw) < header_length + SEED_LENGTH + CHECK_LENGTH + 1:
        raise ValueError("The token line is not one of this encrypter.")

    seed = raw[header_length : header_length + SEED_LENGTH]
    payload = _xor(
        raw[header_length + SEED_LENGTH :],
        _keystream(seed, len(raw) - header_length - SEED_LENGTH),
    )

    checksum, data = payload[:CHECK_LENGTH], payload[CHECK_LENGTH:]

    if hashlib.sha256(data).digest()[:CHECK_LENGTH] != checksum:
        raise ValueError("The token line is damaged, the checksum is wrong.")

    return data.decode("utf-8")
