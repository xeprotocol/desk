"""Anti-spam proof of work (core/pow.go).

result = blake2b_8(nonce_LE || hash_bytes), read as big-endian u64; valid if result >= difficulty.
Block PoW costs about a second of one core in Go; in pure Python expect several seconds,
so callers run it off the event loop. Chat PoW is ~2^18 attempts.
"""

from __future__ import annotations

import hashlib
import os
import struct
import time

DEFAULT_DIFFICULTY = 0xFFFFF80000000000
CHAT_POW_DIFFICULTY = 0xFFFFC00000000000
TEST_DIFFICULTY = 0x0000000000000002


def pow_hash(nonce: int, hash_bytes: bytes) -> int:
    h = hashlib.blake2b(digest_size=8)
    h.update(struct.pack("<Q", nonce & 0xFFFFFFFFFFFFFFFF))
    h.update(hash_bytes)
    return struct.unpack(">Q", h.digest())[0]


def validate_pow(hash_bytes: bytes, nonce: int, difficulty: int) -> bool:
    if difficulty == 0:
        return True
    return pow_hash(nonce, hash_bytes) >= difficulty


def compute_pow(hash_bytes: bytes, difficulty: int, deadline_s: float | None = None) -> int:
    """Brute force from a random start. Raises TimeoutError if deadline_s elapses."""
    if difficulty == 0:
        return 0
    nonce = struct.unpack("<Q", os.urandom(8))[0]
    started = time.monotonic()
    blake = hashlib.blake2b
    pack = struct.pack
    unpack = struct.unpack
    while True:
        h = blake(digest_size=8)
        h.update(pack("<Q", nonce & 0xFFFFFFFFFFFFFFFF))
        h.update(hash_bytes)
        if unpack(">Q", h.digest())[0] >= difficulty:
            return nonce & 0xFFFFFFFFFFFFFFFF
        nonce += 1
        if deadline_s is not None and (nonce & 0xFFFF) == 0 and time.monotonic() - started > deadline_s:
            raise TimeoutError("proof of work deadline exceeded")


def parse_difficulty(hex_str: str | None, default: int) -> int:
    """Nodes advertise thresholds as hex strings in GET /node; "0" means PoW disabled."""
    if hex_str is None or hex_str == "":
        return default
    return int(hex_str, 16)
