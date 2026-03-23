"""
vault/fetch.py — Download → decrypt → decompress → reassemble any file.

Works for both modes stored in the manifest:
  pdf  — reassembles pages in order using pypdf
  raw  — concatenates byte chunks in index order
"""

import io
import os
from typing import Optional

import click
from pypdf import PdfReader, PdfWriter

from vault.crypto   import decrypt_chunk
from vault.manifest import load_manifest


def fetch_file(
    manifest_path: str,
    password:      str,
    output_path:   Optional[str] = None,
    network:       str = "testnet",
) -> str:
    """
    Full fetch pipeline for any file type.
    Returns the path of the reconstructed file.
    """
    from vault.hedera_client import download_bytes

    # ── Load manifest ──────────────────────────────────────────────────────
    manifest = load_manifest(manifest_path)
    original = manifest["original_filename"]
    mode     = manifest.get("mode", "pdf")
    chunks   = manifest["chunks"]
    net      = manifest.get("network", network)

    ext = os.path.splitext(original)[1].lower()
    click.echo(f"📋  File:    {original}  (mode: {mode})")

    # Show compression stats if available
    cs = manifest.get("compression_stats")
    if cs:
        click.echo(f"    Stored size was {cs['overall_saving_pct']}% smaller "
                   f"({cs['total_stored_bytes']:,} → {cs['total_original_bytes']:,} bytes after decompress)")
    click.echo(f"    Chunks: {manifest['total_chunks']}\n")

    # ── Download + decrypt each chunk ─────────────────────────────────────
    decrypted_chunks = []   # list of (index, bytes)

    for idx, chunk in enumerate(chunks, start=1):
        file_id = chunk["hedera_file_id"]

        if mode == "pdf":
            label = f"pages {chunk['page_start']+1}–{chunk['page_end']}"
        else:
            label = f"bytes {chunk['byte_start']:,}–{chunk['byte_end']:,}"

        click.echo(f"  Chunk {idx}/{len(chunks)}  ({label})")
        click.echo(f"    Downloading  FileId: {file_id} ...")

        encrypted = download_bytes(file_id, network=net)

        try:
            plain = decrypt_chunk(encrypted, password)
        except Exception:
            raise ValueError(
                f"Decryption failed for chunk {idx}. "
                "Wrong password or the data has been tampered with."
            )

        was_compressed = chunk.get("compressed", False)
        click.echo(f"    ✓ {len(plain):,} bytes  "
                   f"({'decompressed' if was_compressed else 'raw'})")

        decrypted_chunks.append((chunk["index"], plain))

    # ── Sort chunks by index (order guaranteed but being defensive) ────────
    decrypted_chunks.sort(key=lambda x: x[0])
    ordered = [data for _, data in decrypted_chunks]

    # ── Reassemble ─────────────────────────────────────────────────────────
    if output_path is None:
        stem        = os.path.splitext(original)[0]
        output_path = f"reconstructed_{stem}{ext}"

    if mode == "pdf":
        writer = PdfWriter()
        for chunk_bytes in ordered:
            reader = PdfReader(io.BytesIO(chunk_bytes))
            for page in reader.pages:
                writer.add_page(page)
        with open(output_path, "wb") as f:
            writer.write(f)
    else:
        with open(output_path, "wb") as f:
            for chunk_bytes in ordered:
                f.write(chunk_bytes)

    click.echo(f"\n  Reassembled {len(ordered)} chunk(s) → {output_path}")
    return output_path

