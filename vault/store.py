"""
vault/store.py — Split → compress → encrypt → upload to Hedera.

Supports two modes:
  pdf  — split by page count (uses pypdf). Best for PDFs.
  raw  — split by byte size. Works for any file type.

Pipeline:
  1. Split file into chunks (by page or by bytes)
  2. zlib compress each chunk (skipped automatically if not beneficial)
  3. AES-256-GCM encrypt
  4. Upload to Hedera File Service → get FileId
  5. Build & save manifest JSON
"""

import io
import os
import math
from typing import Optional

import click
from pypdf import PdfReader, PdfWriter

from vault.crypto   import encrypt_chunk
from vault.manifest import build_manifest, save_manifest


# ── Splitters ──────────────────────────────────────────────────────────────────

def _split_pdf(pdf_path: str, chunk_size: int) -> tuple[list[dict], int]:
    """Split a PDF into N-page chunks. Returns (chunks, total_pages)."""
    reader = PdfReader(pdf_path)
    total  = len(reader.pages)
    chunks = []

    for start in range(0, total, chunk_size):
        end    = min(start + chunk_size, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)

        chunks.append({
            "page_start": start,
            "page_end":   end,
            "data":       buf.read(),
        })

    return chunks, total


def _split_raw(file_path: str, chunk_bytes: int) -> tuple[list[dict], int]:
    """
    Split any file into fixed-size byte chunks.
    chunk_bytes defaults to 512 KB — tunable via --chunk-size on raw mode.
    Returns (chunks, total_bytes).
    """
    with open(file_path, "rb") as f:
        raw = f.read()

    total  = len(raw)
    chunks = []

    for i, start in enumerate(range(0, total, chunk_bytes)):
        end = min(start + chunk_bytes, total)
        chunks.append({
            "byte_start": start,
            "byte_end":   end,
            "index":      i,
            "data":       raw[start:end],
        })

    return chunks, total


# ── Main pipeline ──────────────────────────────────────────────────────────────

def store_file(
    file_path:    str,
    password:     str,
    mode:         str  = "pdf",     # "pdf" or "raw"
    chunk_size:   int  = 5,         # pages (pdf) or KB (raw)
    manifest_out: Optional[str] = None,
    network:      str  = "testnet",
) -> str:
    """
    Full store pipeline for any file type.
    Returns the path of the saved manifest.
    """
    from vault.hedera_client import upload_bytes

    filename = os.path.basename(file_path)
    ext      = os.path.splitext(filename)[1].lower()

    # ── Auto-detect mode if not specified ──────────────────────────────────
    if mode == "auto":
        mode = "pdf" if ext == ".pdf" else "raw"

    # ── Split ──────────────────────────────────────────────────────────────
    if mode == "pdf":
        if ext != ".pdf":
            raise ValueError(f"pdf mode requires a .pdf file, got '{ext}'. Use --mode raw.")
        click.echo(f"⚙️   Mode: PDF  |  chunk size: {chunk_size} page(s)")
        raw_chunks, total_size = _split_pdf(file_path, chunk_size)
        size_label = f"{total_size} pages"
    else:
        chunk_bytes = chunk_size * 1024   # chunk_size in KB for raw mode
        click.echo(f"⚙️   Mode: RAW  |  chunk size: {chunk_size} KB")
        raw_chunks, total_size = _split_raw(file_path, chunk_bytes)
        size_label = f"{total_size:,} bytes"

    click.echo(f"    → {len(raw_chunks)} chunk(s) from {size_label}\n")

    # ── Compress + Encrypt + Upload ────────────────────────────────────────
    manifest_chunks    = []
    total_original     = 0
    total_stored       = 0
    chunks_compressed  = 0

    for idx, chunk in enumerate(raw_chunks, start=1):
        if mode == "pdf":
            label = f"pages {chunk['page_start']+1}–{chunk['page_end']}"
        else:
            label = f"bytes {chunk['byte_start']:,}–{chunk['byte_end']:,}"

        click.echo(f"🔐  Chunk {idx}/{len(raw_chunks)}  ({label})")

        # Compress + encrypt (compression is automatic inside encrypt_chunk)
        blob, stats = encrypt_chunk(chunk["data"], password)

        total_original += stats["original"]
        total_stored   += stats["stored"]

        if stats["compressed"]:
            chunks_compressed += 1
            click.echo(f"    ✓ Compressed  {stats['original']:,}B → "
                       f"{stats['stored']:,}B  (saved {stats['saving_pct']}%)")
        else:
            click.echo(f"    — Skipped compression  "
                       f"(already dense, {stats['original']:,}B)")

        # Upload
        memo    = f"{filename} chunk {idx}/{len(raw_chunks)}"
        click.echo(f"    Uploading to Hedera ({network})...")
        file_id = upload_bytes(blob, memo=memo, network=network)
        click.echo(f"    ✓ FileId: {file_id}")

        chunk_meta = {
            "index":          idx - 1,
            "hedera_file_id": file_id,
            "original_bytes": stats["original"],
            "stored_bytes":   stats["stored"],
            "compressed":     stats["compressed"],
        }
        if mode == "pdf":
            chunk_meta["page_start"] = chunk["page_start"]
            chunk_meta["page_end"]   = chunk["page_end"]
        else:
            chunk_meta["byte_start"] = chunk["byte_start"]
            chunk_meta["byte_end"]   = chunk["byte_end"]

        manifest_chunks.append(chunk_meta)

    # ── Summary ────────────────────────────────────────────────────────────
    overall_saving = round((1 - total_stored / total_original) * 100, 1) if total_original else 0
    click.echo(f"\n📊  Compression summary:")
    click.echo(f"    Original : {total_original:,} bytes")
    click.echo(f"    Stored   : {total_stored:,} bytes  ({overall_saving}% saved)")
    click.echo(f"    Chunks compressed: {chunks_compressed}/{len(raw_chunks)}")

    # ── Manifest ───────────────────────────────────────────────────────────
    manifest = build_manifest(
        original_filename = filename,
        total_size        = total_size,
        mode              = mode,
        chunk_size        = chunk_size,
        chunks            = manifest_chunks,
        network           = network,
        compression_stats = {
            "total_original_bytes": total_original,
            "total_stored_bytes":   total_stored,
            "overall_saving_pct":   overall_saving,
            "chunks_compressed":    chunks_compressed,
        },
    )
    return save_manifest(manifest, manifest_out, file_path)

