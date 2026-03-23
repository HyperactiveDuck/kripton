"""
vault/crypto.py — AES-256-GCM encryption + optional zlib compression.

Pipeline per chunk:
  1. (optional) zlib.compress(data, level=6)  — only kept if it actually shrinks
  2. AES-256-GCM encrypt with a PBKDF2-derived key

Wire format (bytes on the wire / on Hedera):
  [ compressed_flag (1) ][ salt (16) ][ iv (12) ][ ciphertext + GCM tag ]

  compressed_flag:
    0x01 = data was compressed before encrypting  → decompress after decrypt
    0x00 = data was NOT compressed (already dense, e.g. JPEG-heavy PDF)

Compression is transparent to callers — encrypt_chunk decides automatically,
decrypt_chunk reads the flag and decompresses if needed.
"""

import os
import zlib
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ── Constants ──────────────────────────────────────────────────────────────────
SALT_LEN      = 16
IV_LEN        = 12
KEY_LEN       = 32          # 256-bit AES key
PBKDF2_ITERS  = 600_000     # NIST SP 800-132 recommendation (2023)
FLAG_LEN      = 1           # 1-byte compression flag at start of blob
COMPRESS_FLAG = b"\x01"
RAW_FLAG      = b"\x00"
ZLIB_LEVEL    = 6           # 1 (fast) – 9 (max). 6 is the zlib default sweet spot.
MIN_GAIN_PCT  = 5           # skip compression if saving is less than 5%


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 256-bit AES key from a password + salt using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LEN,
        salt=salt,
        iterations=PBKDF2_ITERS,
    )
    return kdf.derive(password.encode("utf-8"))


def _try_compress(data: bytes) -> tuple[bytes, bool]:
    """
    Attempt zlib compression. Returns (payload, was_compressed).
    Skips compression if the result isn't at least MIN_GAIN_PCT smaller.
    """
    compressed = zlib.compress(data, level=ZLIB_LEVEL)
    saving_pct = (1 - len(compressed) / len(data)) * 100
    if saving_pct >= MIN_GAIN_PCT:
        return compressed, True
    return data, False


def encrypt_chunk(data: bytes, password: str) -> tuple[bytes, dict]:
    """
    Optionally compress, then encrypt `data` with AES-256-GCM.

    Returns:
      blob  — bytes ready to upload to Hedera
      stats — {"original": int, "stored": int, "compressed": bool, "saving_pct": float}

    Wire format: flag(1) || salt(16) || iv(12) || ciphertext+tag
    """
    # 1 — try compression
    payload, compressed = _try_compress(data)

    # 2 — encrypt
    salt = os.urandom(SALT_LEN)
    iv   = os.urandom(IV_LEN)
    key  = _derive_key(password, salt)

    aesgcm     = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, payload, None)

    flag = COMPRESS_FLAG if compressed else RAW_FLAG
    blob = flag + salt + iv + ciphertext

    saving_pct = round((1 - len(payload) / len(data)) * 100, 1) if compressed else 0.0
    stats = {
        "original":    len(data),
        "stored":      len(blob),
        "compressed":  compressed,
        "saving_pct":  saving_pct,
    }
    return blob, stats


def decrypt_chunk(blob: bytes, password: str) -> bytes:
    """
    Decrypt (and optionally decompress) a blob produced by encrypt_chunk.
    Raises InvalidTag if the password is wrong or data is tampered with.
    """
    flag       = blob[:FLAG_LEN]
    salt       = blob[FLAG_LEN : FLAG_LEN + SALT_LEN]
    iv         = blob[FLAG_LEN + SALT_LEN : FLAG_LEN + SALT_LEN + IV_LEN]
    ciphertext = blob[FLAG_LEN + SALT_LEN + IV_LEN :]

    key    = _derive_key(password, salt)
    aesgcm = AESGCM(key)
    plain  = aesgcm.decrypt(iv, ciphertext, None)

    if flag == COMPRESS_FLAG:
        plain = zlib.decompress(plain)

    return plain
