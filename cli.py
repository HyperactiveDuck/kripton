#!/usr/bin/env python3
"""
HashVault CLI — Split, compress, encrypt, and store files on Hedera Hashgraph.
Usage:
  python cli.py store  <file>          --password <pass>
  python cli.py fetch  <manifest.json> --password <pass> --out <output>
  python cli.py info   <manifest.json>
"""

import click
from vault.store    import store_file
from vault.fetch    import fetch_file
from vault.manifest import load_manifest


@click.group()
def cli():
    """🔐 HashVault — Secure file storage on Hedera Hashgraph."""
    pass


# ── STORE ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--password", "-p", prompt=True, hide_input=True,
              confirmation_prompt=True, help="Encryption password.")
@click.option("--mode", "-m", default="auto",
              type=click.Choice(["auto", "pdf", "raw"]), show_default=True,
              help="Split mode. 'auto' picks pdf for .pdf files, raw for everything else.")
@click.option("--chunk-size", "-c", default=5, show_default=True,
              help="Pages per chunk (pdf mode) or KB per chunk (raw mode).")
@click.option("--manifest", default=None,
              help="Output path for manifest JSON (default: <filename>.manifest.json).")
@click.option("--network", default="testnet", type=click.Choice(["testnet", "mainnet"]),
              show_default=True, help="Hedera network.")
def store(file_path, password, mode, chunk_size, manifest, network):
    """Compress, encrypt, and upload a file to Hedera File Service."""
    click.echo(f"\n  File:       {file_path}")
    click.echo(f"  Mode:       {mode}  |  chunk size: {chunk_size}")
    click.echo(f"  Network:    {network}\n")

    manifest_path = store_file(
        file_path=file_path,
        password=password,
        mode=mode,
        chunk_size=chunk_size,
        manifest_out=manifest,
        network=network,
    )
    click.echo(f"\n✅  Done! Manifest saved to: {manifest_path}")
    click.echo("    Keep this file — it's your map to reconstruct the original.\n")


# ── FETCH ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("manifest_path", type=click.Path(exists=True))
@click.option("--password", "-p", prompt=True, hide_input=True,
              help="Decryption password.")
@click.option("--out", "-o", default=None,
              help="Output file path (default: reconstructed_<original_name>.<ext>).")
@click.option("--network", default="testnet", type=click.Choice(["testnet", "mainnet"]),
              show_default=True, help="Hedera network.")
def fetch(manifest_path, password, out, network):
    """Download, decrypt, and reassemble a file from Hedera File Service."""
    click.echo(f"\n📋  Manifest:  {manifest_path}")
    click.echo(f"🌐  Network:   {network}\n")

    output_path = fetch_file(
        manifest_path=manifest_path,
        password=password,
        output_path=out,
        network=network,
    )
    click.echo(f"\n  Reconstructed file saved to: {output_path}\n")


# ── INFO ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("manifest_path", type=click.Path(exists=True))
def info(manifest_path):
    """Display metadata from a HashVault manifest (no password needed)."""
    m  = load_manifest(manifest_path)
    cs = m.get("compression_stats", {})
    mode = m.get("mode", "pdf")

    click.echo(f"\n📋  Manifest:  {manifest_path}")
    click.echo(f"   File      : {m['original_filename']}")
    click.echo(f"   Mode      : {mode}")
    click.echo(f"   Total size: {m['total_size']} {'pages' if mode == 'pdf' else 'bytes'}")
    click.echo(f"   Chunks    : {m['total_chunks']}  (chunk_size={m.get('chunk_size', '?')})")
    click.echo(f"   Created   : {m['created_at']}")
    click.echo(f"   Network   : {m['network']}")

    if cs:
        click.echo(f"\n   Compression:")
        click.echo(f"     Original : {cs.get('total_original_bytes', '?'):,} bytes")
        click.echo(f"     Stored   : {cs.get('total_stored_bytes', '?'):,} bytes")
        click.echo(f"     Saved    : {cs.get('overall_saving_pct', '?')}%")
        click.echo(f"     Chunks compressed: {cs.get('chunks_compressed', '?')}/{m['total_chunks']}")

    click.echo(f"\n   Chunk FileIDs on Hedera:")
    for chunk in m["chunks"]:
        i = chunk.get("index", "?")
        fid = chunk["hedera_file_id"]
        comp = "z" if chunk.get("compressed") else " "
        if mode == "pdf":
            pos = f"pages {chunk.get('page_start', '?')+1}–{chunk.get('page_end', '?')}"
        else:
            pos = f"bytes {chunk.get('byte_start', '?'):,}–{chunk.get('byte_end', '?'):,}"
        click.echo(f"     [{i:02}] [{comp}] {pos}  →  {fid}")

    click.echo(f"\n   [z] = compressed chunk\n")


if __name__ == "__main__":
    cli()
