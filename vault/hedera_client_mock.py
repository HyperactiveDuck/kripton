"""
vault/hedera_client_mock.py — Local filesystem mock of Hedera File Service.

Activated when HASHVAULT_MOCK=1 is set in the environment.
Stores encrypted blobs in .hashvault_store/<file_id>.bin so the full
pipeline can be tested without any network or real Hedera credentials.

FileIds are fake but structurally identical to real ones: 0.0.<counter>
starting at 0.0.5000000 to avoid collisions with real testnet IDs.

Drop-in replacement for hedera_client.py — same three public functions:
  upload_bytes(data, memo, network)  → str (FileId)
  download_bytes(file_id_str, network) → bytes
  delete_file(file_id_str, network)
"""

import os
import json
import time
import threading

# Thread-safe counter for generating fake FileIds
_counter_lock = threading.Lock()
_BASE_ID      = 5_000_000
_STORE_DIR    = os.path.join(os.path.expanduser("~"), ".hashvault_store")

# ── Internal helpers ───────────────────────────────────────────────────────────

def _store_dir() -> str:
    os.makedirs(_STORE_DIR, exist_ok=True)
    return _STORE_DIR


def _index_path() -> str:
    return os.path.join(_store_dir(), "index.json")


def _load_index() -> dict:
    p = _index_path()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"next_id": _BASE_ID, "files": {}}


def _save_index(index: dict) -> None:
    with open(_index_path(), "w") as f:
        json.dump(index, f, indent=2)


def _next_file_id() -> str:
    with _counter_lock:
        index = _load_index()
        fid   = f"0.0.{index['next_id']}"
        index["next_id"] += 1
        _save_index(index)
    return fid


# ── Public API (mirrors hedera_client.py exactly) ─────────────────────────────

def upload_bytes(data: bytes, memo: str = "", network: str = "testnet") -> str:
    """
    'Upload' bytes by writing them to ~/.hashvault_store/<file_id>.bin.
    Returns the mock FileId string.
    """
    file_id  = _next_file_id()
    blob_path = os.path.join(_store_dir(), f"{file_id.replace('.', '_')}.bin")

    with open(blob_path, "wb") as f:
        f.write(data)

    # Record in index
    index = _load_index()
    index["files"][file_id] = {
        "path":    blob_path,
        "memo":    memo,
        "size":    len(data),
        "network": network,
        "created": time.time(),
    }
    _save_index(index)

    return file_id


def download_bytes(file_id_str: str, network: str = "testnet") -> bytes:
    """
    'Download' bytes by reading from ~/.hashvault_store/<file_id>.bin.
    Raises FileNotFoundError if the FileId doesn't exist.
    """
    index = _load_index()
    if file_id_str not in index["files"]:
        raise FileNotFoundError(
            f"Mock FileId '{file_id_str}' not found in local store.\n"
            f"Store dir: {_STORE_DIR}"
        )

    blob_path = index["files"][file_id_str]["path"]
    with open(blob_path, "rb") as f:
        return f.read()


def delete_file(file_id_str: str, network: str = "testnet") -> None:
    """
    'Delete' a file by removing it from the local store.
    """
    index = _load_index()
    if file_id_str not in index["files"]:
        return

    blob_path = index["files"][file_id_str]["path"]
    if os.path.exists(blob_path):
        os.remove(blob_path)

    del index["files"][file_id_str]
    _save_index(index)


def list_files() -> list[dict]:
    """List all mock-stored files (not in real Hedera client — debug helper)."""
    index = _load_index()
    return [
        {"file_id": fid, **meta}
        for fid, meta in index["files"].items()
    ]
