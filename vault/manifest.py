"""
vault/manifest.py — Build, save, and load the HashVault manifest.

The manifest records everything needed to reconstruct the original file:
  - Original filename, size, and split mode (pdf / raw)
  - Per-chunk metadata: position, Hedera FileId, compression stats
  - Overall compression summary
  - Network info and timestamp

No encryption keys or plaintext content is ever stored here.
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional


def build_manifest(
    original_filename: str,
    total_size:        int,         # pages (pdf) or bytes (raw)
    mode:              str,         # "pdf" or "raw"
    chunk_size:        int,
    chunks:            list[dict],
    network:           str,
    compression_stats: dict,
) -> dict:
    """Assemble the manifest dictionary."""
    return {
        "version":           "2.0",
        "original_filename": original_filename,
        "mode":              mode,
        "total_size":        total_size,
        "total_chunks":      len(chunks),
        "chunk_size":        chunk_size,
        "network":           network,
        "created_at":        datetime.now(timezone.utc).isoformat(),
        "compression_stats": compression_stats,
        "chunks":            chunks,
    }


def save_manifest(manifest: dict, out_path: Optional[str], file_path: str) -> str:
    """Write manifest JSON to disk. Returns the path used."""
    if out_path is None:
        stem     = os.path.splitext(os.path.basename(file_path))[0]
        out_dir  = os.path.dirname(os.path.abspath(file_path))
        out_path = os.path.join(out_dir, f"{stem}.manifest.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return out_path


def load_manifest(manifest_path: str) -> dict:
    """Load and validate a manifest from disk."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    required = {"version", "original_filename", "total_chunks", "chunks", "network"}
    missing  = required - data.keys()
    if missing:
        raise ValueError(f"Manifest is missing required fields: {missing}")

    return data

