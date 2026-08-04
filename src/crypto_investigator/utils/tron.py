from hashlib import sha256

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def tron_address_to_base58(value: str) -> str:
    if value.startswith("T"):
        return value
    normalized = value.removeprefix("0x")
    if len(normalized) != 42 or not normalized.startswith("41"):
        raise ValueError("TRON address must be Base58 or 21-byte 0x41 hex")
    payload = bytes.fromhex(normalized)
    checksum = sha256(sha256(payload).digest()).digest()[:4]
    number = int.from_bytes(payload + checksum, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58_ALPHABET[remainder] + encoded
    leading_zeroes = len(payload + checksum) - len((payload + checksum).lstrip(b"\0"))
    return "1" * leading_zeroes + encoded
