#!/usr/bin/env python3
"""
HashVault Desktop GUI — CustomTkinter front-end for the vault pipeline.

Launch:
    HASHVAULT_MOCK=1 python gui.py        # mock mode
    python gui.py                          # real Hedera (needs creds in env)
"""

import os
import io
import sys
import threading
import customtkinter as ctk
from tkinter import filedialog, END

# ── Appearance ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT_FAMILY = "Segoe UI"
ACCENT      = "#1f6feb"
BG_DARK     = "#0d1117"
BG_CARD     = "#161b22"
BG_INPUT    = "#21262d"
FG_TEXT     = "#c9d1d9"
FG_DIM      = "#8b949e"
BORDER_CLR  = "#30363d"
SUCCESS     = "#3fb950"
WARNING     = "#d29922"
ERROR       = "#f85149"
PENDING     = "#484f58"


# ── Redirect click.echo / print into a CTkTextbox ────────────────────────────

class TextboxWriter(io.TextIOBase):
    """File-like object that writes to a CTkTextbox. Thread-safe via .after()."""

    def __init__(self, textbox: ctk.CTkTextbox):
        self._tb = textbox

    def write(self, s: str):
        if s:
            self._tb.after(0, self._append, s)
        return len(s) if s else 0

    def _append(self, s: str):
        self._tb.configure(state="normal")
        self._tb.insert(END, s)
        self._tb.see(END)
        self._tb.configure(state="disabled")

    def flush(self):
        pass


# ── Helper widgets ────────────────────────────────────────────────────────────

class FilePickerRow(ctk.CTkFrame):
    """A row with a label, readonly entry, and Browse button."""

    def __init__(self, master, label: str, filetypes=None, save=False, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._filetypes = filetypes or [("All files", "*.*")]
        self._save = save
        self._on_change = None

        self._label = ctk.CTkLabel(self, text=label, width=100, anchor="w",
                                   font=ctk.CTkFont(family=FONT_FAMILY, size=13))
        self._label.pack(side="left", padx=(0, 8))

        self._var = ctk.StringVar()
        self._entry = ctk.CTkEntry(self, textvariable=self._var, width=340,
                                   state="readonly", fg_color=BG_INPUT,
                                   border_color=BORDER_CLR, text_color=FG_TEXT,
                                   font=ctk.CTkFont(family=FONT_FAMILY, size=12))
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._btn = ctk.CTkButton(self, text="Browse", width=80,
                                  command=self._browse, fg_color=ACCENT,
                                  hover_color="#388bfd",
                                  font=ctk.CTkFont(family=FONT_FAMILY, size=12))
        self._btn.pack(side="left")

    def set_on_change(self, callback):
        self._on_change = callback

    def _browse(self):
        if self._save:
            path = filedialog.asksaveasfilename(filetypes=self._filetypes)
        else:
            path = filedialog.askopenfilename(filetypes=self._filetypes)
        if path:
            self._var.set(path)
            if self._on_change:
                self._on_change(path)

    @property
    def path(self) -> str:
        return self._var.get()


class PasswordRow(ctk.CTkFrame):
    """A row with a label and password entry."""

    def __init__(self, master, label: str = "Password", **kw):
        super().__init__(master, fg_color="transparent", **kw)

        ctk.CTkLabel(self, text=label, width=100, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=13)).pack(side="left", padx=(0, 8))

        self._var = ctk.StringVar()
        self._entry = ctk.CTkEntry(self, textvariable=self._var, show="•",
                                   width=340, fg_color=BG_INPUT,
                                   border_color=BORDER_CLR, text_color=FG_TEXT,
                                   font=ctk.CTkFont(family=FONT_FAMILY, size=12))
        self._entry.pack(side="left", fill="x", expand=True)

    @property
    def password(self) -> str:
        return self._var.get()


# ── Pipeline Step Indicator ──────────────────────────────────────────────────

class StepIndicator(ctk.CTkFrame):
    """A single step in the pipeline: icon + label + status text."""

    def __init__(self, master, label: str, **kw):
        super().__init__(master, fg_color="transparent", **kw)

        self._icon = ctk.CTkLabel(self, text="○", width=22,
                                  font=ctk.CTkFont(size=14),
                                  text_color=PENDING)
        self._icon.pack(side="left", padx=(0, 6))

        self._label = ctk.CTkLabel(self, text=label, width=90, anchor="w",
                                   font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                                   text_color=FG_DIM)
        self._label.pack(side="left", padx=(0, 6))

        self._status = ctk.CTkLabel(self, text="", anchor="w",
                                    font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                    text_color=FG_DIM)
        self._status.pack(side="left", fill="x", expand=True)

    def set_pending(self, status_text=""):
        self._icon.after(0, lambda: self._icon.configure(text="○", text_color=PENDING))
        self._label.after(0, lambda: self._label.configure(text_color=FG_DIM))
        self._status.after(0, lambda: self._status.configure(text=status_text, text_color=FG_DIM))

    def set_active(self, status_text="In progress…"):
        self._icon.after(0, lambda: self._icon.configure(text="◉", text_color=WARNING))
        self._label.after(0, lambda: self._label.configure(text_color=FG_TEXT))
        self._status.after(0, lambda: self._status.configure(text=status_text, text_color=WARNING))

    def set_done(self, status_text="Done"):
        self._icon.after(0, lambda: self._icon.configure(text="✓", text_color=SUCCESS))
        self._label.after(0, lambda: self._label.configure(text_color=SUCCESS))
        self._status.after(0, lambda: self._status.configure(text=status_text, text_color=SUCCESS))

    def set_error(self, status_text="Failed"):
        self._icon.after(0, lambda: self._icon.configure(text="✗", text_color=ERROR))
        self._label.after(0, lambda: self._label.configure(text_color=ERROR))
        self._status.after(0, lambda: self._status.configure(text=status_text, text_color=ERROR))


class PipelinePanel(ctk.CTkFrame):
    """A panel showing a vertical list of pipeline steps with a title."""

    def __init__(self, master, title: str, steps: list[str], **kw):
        super().__init__(master, fg_color=BG_INPUT, corner_radius=8,
                         border_color=BORDER_CLR, border_width=1, **kw)

        ctk.CTkLabel(self, text=title, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12, weight="bold"),
                     text_color=FG_TEXT).pack(fill="x", padx=10, pady=(8, 4))

        self._steps: dict[str, StepIndicator] = {}
        for name in steps:
            si = StepIndicator(self, name)
            si.pack(fill="x", padx=10, pady=1)
            self._steps[name] = si

    def __getitem__(self, name: str) -> StepIndicator:
        return self._steps[name]

    def reset_all(self):
        for si in self._steps.values():
            si.set_pending()


# ── File Info Bar ─────────────────────────────────────────────────────────────

class FileInfoBar(ctk.CTkFrame):
    """Shows file size, type, and estimated compression before processing."""

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG_INPUT, corner_radius=8,
                         border_color=BORDER_CLR, border_width=1, **kw)

        self._info = ctk.CTkLabel(self, text="No file selected",
                                  anchor="w", justify="left",
                                  font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                  text_color=FG_DIM)
        self._info.pack(fill="x", padx=10, pady=6)

    def update_for_file(self, file_path: str):
        """Analyse a file and show its stats + compression estimate."""
        try:
            import zlib
            size = os.path.getsize(file_path)
            name = os.path.basename(file_path)
            ext  = os.path.splitext(name)[1].lower()

            # Quick compression estimate on first 64KB
            with open(file_path, "rb") as f:
                sample = f.read(65536)
            compressed = zlib.compress(sample, 6)
            ratio = (1 - len(compressed) / len(sample)) * 100 if sample else 0

            # Human-readable size
            if size < 1024:
                sz_str = f"{size} B"
            elif size < 1024 * 1024:
                sz_str = f"{size / 1024:.1f} KB"
            else:
                sz_str = f"{size / (1024 * 1024):.1f} MB"

            # Compressibility assessment
            if ratio >= 30:
                comp_msg = f"🟢 Highly compressible (~{ratio:.0f}% savings expected)"
            elif ratio >= 5:
                comp_msg = f"🟡 Moderately compressible (~{ratio:.0f}% savings expected)"
            else:
                comp_msg = f"🔴 Low compressibility (~{ratio:.0f}%) — already dense"

            # File type hint
            type_hints = {
                ".pdf": "📄 PDF document",
                ".png": "🖼️ PNG image",
                ".jpg": "🖼️ JPEG image", ".jpeg": "🖼️ JPEG image",
                ".txt": "📝 Text file",
                ".zip": "📦 ZIP archive",
                ".mp4": "🎬 MP4 video",
                ".mp3": "🎵 MP3 audio",
            }
            ftype = type_hints.get(ext, f"📁 {ext.upper()} file" if ext else "📁 File")

            text = f"{ftype}  •  {name}  •  {sz_str}\n{comp_msg}"
            self._info.configure(text=text, text_color=FG_TEXT)

        except Exception:
            self._info.configure(text="Could not read file info", text_color=ERROR)

    def clear(self):
        self._info.configure(text="No file selected", text_color=FG_DIM)


# ── Store Tab ─────────────────────────────────────────────────────────────────

STORE_STEPS = ["Split", "Compress", "Encrypt", "Upload", "Manifest"]

class StoreTab(ctk.CTkFrame):

    def __init__(self, master, log_writer, settings, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._log = log_writer
        self._settings = settings

        # File picker
        self._file = FilePickerRow(self, "File")
        self._file.pack(fill="x", pady=(8, 4), padx=12)

        # File info bar (compression preview)
        self._file_info = FileInfoBar(self)
        self._file_info.pack(fill="x", pady=(0, 4), padx=12)
        self._file.set_on_change(self._file_info.update_for_file)

        # Password
        self._pw = PasswordRow(self)
        self._pw.pack(fill="x", pady=4, padx=12)

        # Options row
        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.pack(fill="x", pady=4, padx=12)

        ctk.CTkLabel(opts, text="Mode", width=100, anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=13)).pack(side="left", padx=(0, 8))
        self._mode = ctk.CTkOptionMenu(opts, values=["auto", "pdf", "raw"], width=100,
                                       fg_color=BG_INPUT, button_color=ACCENT,
                                       button_hover_color="#388bfd",
                                       font=ctk.CTkFont(family=FONT_FAMILY, size=12))
        self._mode.set("auto")
        self._mode.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(opts, text="Chunk size", anchor="w",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=13)).pack(side="left", padx=(0, 8))
        self._chunk = ctk.CTkEntry(opts, width=60, fg_color=BG_INPUT,
                                   border_color=BORDER_CLR, text_color=FG_TEXT,
                                   font=ctk.CTkFont(family=FONT_FAMILY, size=12))
        self._chunk.insert(0, "5")
        self._chunk.pack(side="left")

        # Store button
        self._btn = ctk.CTkButton(self, text="🔐  Store File", height=40,
                                  fg_color=ACCENT, hover_color="#388bfd",
                                  font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                                  command=self._run)
        self._btn.pack(pady=(8, 4), padx=12)

        # Pipeline status panel
        self._pipeline = PipelinePanel(self, "Pipeline Status", STORE_STEPS)
        self._pipeline.pack(fill="x", padx=12, pady=(4, 8))

    def _run(self):
        path = self._file.path
        pw   = self._pw.password
        if not path or not pw:
            self._log.write("⚠️  Please select a file and enter a password.\n")
            return

        mode       = self._mode.get()
        chunk_size = int(self._chunk.get())
        network    = self._settings["network"]()

        self._settings["apply_mock"]()
        self._pipeline.reset_all()
        self._btn.configure(state="disabled", text="⏳  Storing…")

        threading.Thread(target=self._do_store,
                         args=(path, pw, mode, chunk_size, network),
                         daemon=True).start()

    def _do_store(self, path, pw, mode, chunk_size, network):
        old_stdout = sys.stdout
        sys.stdout = self._log
        pp = self._pipeline
        try:
            import math
            from vault.crypto   import encrypt_chunk
            from vault.manifest import build_manifest, save_manifest

            filename = os.path.basename(path)
            ext      = os.path.splitext(filename)[1].lower()

            if mode == "auto":
                mode = "pdf" if ext == ".pdf" else "raw"

            # ── Step 1: Split ─────────────────────────────────────────────
            pp["Split"].set_active("Splitting file…")

            if mode == "pdf":
                from vault.store import _split_pdf
                raw_chunks, total_size = _split_pdf(path, chunk_size)
                size_label = f"{total_size} pages"
            else:
                from vault.store import _split_raw
                chunk_bytes = chunk_size * 1024
                raw_chunks, total_size = _split_raw(path, chunk_bytes)
                size_label = f"{total_size:,} bytes"

            n = len(raw_chunks)
            pp["Split"].set_done(f"{n} chunk(s) from {size_label}")
            self._log.write(f"✂️  Split into {n} chunk(s) from {size_label}\n")

            # ── Step 2–4 per chunk: Compress → Encrypt → Upload ───────────
            manifest_chunks   = []
            total_original    = 0
            total_stored      = 0
            chunks_compressed = 0

            for idx, chunk in enumerate(raw_chunks, start=1):
                chunk_label = f"Chunk {idx}/{n}"

                # Compress + Encrypt (handled together by encrypt_chunk)
                pp["Compress"].set_active(f"{chunk_label}…")
                pp["Encrypt"].set_active(f"{chunk_label}…")

                blob, stats = encrypt_chunk(chunk["data"], pw)
                total_original += stats["original"]
                total_stored   += stats["stored"]

                if stats["compressed"]:
                    chunks_compressed += 1
                    comp_msg = f"{chunk_label}: {stats['original']:,}B → {stats['stored']:,}B (saved {stats['saving_pct']}%)"
                    pp["Compress"].set_done(comp_msg)
                    self._log.write(f"🗜️  {comp_msg}\n")
                else:
                    pp["Compress"].set_done(f"{chunk_label}: skipped (already dense)")
                    self._log.write(f"🗜️  {chunk_label}: skipped compression (already dense, {stats['original']:,}B)\n")

                pp["Encrypt"].set_done(f"{chunk_label}: AES-256-GCM ✓")
                self._log.write(f"🔐  {chunk_label}: encrypted ✓\n")

                # Upload
                pp["Upload"].set_active(f"{chunk_label}…")
                from vault.hedera_client import upload_bytes
                memo    = f"{filename} chunk {idx}/{n}"
                file_id = upload_bytes(blob, memo=memo, network=network)
                pp["Upload"].set_done(f"{chunk_label} → {file_id}")
                self._log.write(f"☁️  {chunk_label}: uploaded → {file_id}\n")

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

            # ── Summary ───────────────────────────────────────────────────
            overall_saving = round((1 - total_stored / total_original) * 100, 1) if total_original else 0

            # Final compress status
            pp["Compress"].set_done(f"{chunks_compressed}/{n} compressed | saved {overall_saving}%")
            pp["Upload"].set_done(f"All {n} chunk(s) uploaded")
            pp["Encrypt"].set_done(f"All {n} chunk(s) encrypted")

            # ── Step 5: Manifest ──────────────────────────────────────────
            pp["Manifest"].set_active("Saving manifest…")
            manifest = build_manifest(
                original_filename=filename,
                total_size=total_size,
                mode=mode,
                chunk_size=chunk_size,
                chunks=manifest_chunks,
                network=network,
                compression_stats={
                    "total_original_bytes": total_original,
                    "total_stored_bytes":   total_stored,
                    "overall_saving_pct":   overall_saving,
                    "chunks_compressed":    chunks_compressed,
                },
            )
            manifest_path = save_manifest(manifest, None, path)
            pp["Manifest"].set_done(os.path.basename(manifest_path))

            self._log.write(f"\n📊  Compression: {total_original:,}B → {total_stored:,}B ({overall_saving}% saved)\n")
            self._log.write(f"✅  Manifest saved to: {manifest_path}\n\n")

        except Exception as e:
            self._log.write(f"\n❌  Error: {e}\n")
            # Mark current active steps as error
            for name in STORE_STEPS:
                si = pp[name]
                # Only mark error on steps that are still active
            pp["Split"].set_error(str(e)[:60]) if "Split" in str(e) else None
        finally:
            sys.stdout = old_stdout
            self._btn.after(0, lambda: self._btn.configure(state="normal",
                                                           text="🔐  Store File"))


# ── Fetch Tab ─────────────────────────────────────────────────────────────────

FETCH_STEPS = ["Download", "Decrypt", "Decompress", "Reassemble"]

class FetchTab(ctk.CTkFrame):

    def __init__(self, master, log_writer, settings, **kw):
        super().__init__(master, fg_color="transparent", **kw)
        self._log = log_writer
        self._settings = settings

        self._manifest = FilePickerRow(self, "Manifest",
                                       filetypes=[("JSON", "*.json"), ("All", "*.*")])
        self._manifest.pack(fill="x", pady=(8, 4), padx=12)

        self._pw = PasswordRow(self)
        self._pw.pack(fill="x", pady=4, padx=12)

        self._out = FilePickerRow(self, "Output", save=True)
        self._out.pack(fill="x", pady=4, padx=12)

        self._btn = ctk.CTkButton(self, text="📥  Fetch File", height=40,
                                  fg_color=ACCENT, hover_color="#388bfd",
                                  font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                                  command=self._run)
        self._btn.pack(pady=(8, 4), padx=12)

        # Pipeline status panel
        self._pipeline = PipelinePanel(self, "Pipeline Status", FETCH_STEPS)
        self._pipeline.pack(fill="x", padx=12, pady=(4, 8))

    def _run(self):
        manifest = self._manifest.path
        pw       = self._pw.password
        if not manifest or not pw:
            self._log.write("⚠️  Please select a manifest and enter a password.\n")
            return

        out     = self._out.path or None
        network = self._settings["network"]()

        self._settings["apply_mock"]()
        self._pipeline.reset_all()
        self._btn.configure(state="disabled", text="⏳  Fetching…")

        threading.Thread(target=self._do_fetch,
                         args=(manifest, pw, out, network),
                         daemon=True).start()

    def _do_fetch(self, manifest_path, pw, out, network):
        old_stdout = sys.stdout
        sys.stdout = self._log
        pp = self._pipeline
        try:
            from vault.manifest      import load_manifest
            from vault.crypto        import decrypt_chunk
            from vault.hedera_client import download_bytes

            manifest = load_manifest(manifest_path)
            original = manifest["original_filename"]
            mode     = manifest.get("mode", "pdf")
            chunks   = manifest["chunks"]
            net      = manifest.get("network", network)
            n        = len(chunks)

            ext = os.path.splitext(original)[1].lower()
            self._log.write(f"📋  {original}  (mode: {mode}, {n} chunks)\n")

            decrypted_chunks = []

            for idx, chunk in enumerate(chunks, start=1):
                file_id = chunk["hedera_file_id"]
                chunk_label = f"Chunk {idx}/{n}"

                # Download
                pp["Download"].set_active(f"{chunk_label} ({file_id})…")
                encrypted = download_bytes(file_id, network=net)
                pp["Download"].set_done(f"{chunk_label}: {len(encrypted):,}B")
                self._log.write(f"📥  {chunk_label}: downloaded {len(encrypted):,}B from {file_id}\n")

                # Decrypt
                pp["Decrypt"].set_active(f"{chunk_label}…")
                try:
                    plain = decrypt_chunk(encrypted, pw)
                except Exception:
                    pp["Decrypt"].set_error(f"{chunk_label}: wrong password or tampered")
                    raise ValueError(f"Decryption failed for chunk {idx}. Wrong password or tampered data.")

                pp["Decrypt"].set_done(f"{chunk_label}: {len(plain):,}B ✓")
                self._log.write(f"🔓  {chunk_label}: decrypted → {len(plain):,}B\n")

                # Decompress indicator
                was_compressed = chunk.get("compressed", False)
                if was_compressed:
                    pp["Decompress"].set_done(f"{chunk_label}: decompressed ✓")
                    self._log.write(f"🗜️  {chunk_label}: decompressed ✓\n")
                else:
                    pp["Decompress"].set_done(f"{chunk_label}: raw (no compression)")

                decrypted_chunks.append((chunk["index"], plain))

            # Final status
            pp["Download"].set_done(f"All {n} chunk(s) downloaded")
            pp["Decrypt"].set_done(f"All {n} chunk(s) decrypted")

            # Reassemble
            pp["Reassemble"].set_active("Merging chunks…")
            decrypted_chunks.sort(key=lambda x: x[0])
            ordered = [data for _, data in decrypted_chunks]

            if out is None:
                stem = os.path.splitext(original)[0]
                out  = f"reconstructed_{stem}{ext}"

            if mode == "pdf":
                from pypdf import PdfReader, PdfWriter
                writer = PdfWriter()
                for chunk_bytes in ordered:
                    reader = PdfReader(io.BytesIO(chunk_bytes))
                    for page in reader.pages:
                        writer.add_page(page)
                with open(out, "wb") as f:
                    writer.write(f)
            else:
                with open(out, "wb") as f:
                    for chunk_bytes in ordered:
                        f.write(chunk_bytes)

            pp["Reassemble"].set_done(os.path.basename(out))
            self._log.write(f"\n✅  Reassembled {n} chunk(s) → {out}\n\n")

        except Exception as e:
            self._log.write(f"\n❌  Error: {e}\n")
        finally:
            sys.stdout = old_stdout
            self._btn.after(0, lambda: self._btn.configure(state="normal",
                                                           text="📥  Fetch File"))


# ── Info Tab ──────────────────────────────────────────────────────────────────

class InfoTab(ctk.CTkFrame):

    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", **kw)

        self._manifest = FilePickerRow(self, "Manifest",
                                       filetypes=[("JSON", "*.json"), ("All", "*.*")])
        self._manifest.pack(fill="x", pady=(8, 4), padx=12)

        self._btn = ctk.CTkButton(self, text="🔍  Inspect", height=36,
                                  fg_color=ACCENT, hover_color="#388bfd",
                                  font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
                                  command=self._run)
        self._btn.pack(pady=(8, 4), padx=12)

        self._info_box = ctk.CTkTextbox(self, height=250, state="disabled",
                                        fg_color=BG_INPUT, text_color=FG_TEXT,
                                        border_color=BORDER_CLR, border_width=1,
                                        font=ctk.CTkFont(family="Courier New", size=12))
        self._info_box.pack(fill="both", expand=True, padx=12, pady=(4, 8))

    def _run(self):
        path = self._manifest.path
        if not path:
            return

        try:
            from vault.manifest import load_manifest
            m    = load_manifest(path)
            cs   = m.get("compression_stats", {})
            mode = m.get("mode", "pdf")

            lines = [
                f"📋  Manifest:  {path}",
                f"   File       : {m['original_filename']}",
                f"   Mode       : {mode}",
                f"   Total size : {m['total_size']} {'pages' if mode == 'pdf' else 'bytes'}",
                f"   Chunks     : {m['total_chunks']}  (chunk_size={m.get('chunk_size', '?')})",
                f"   Created    : {m['created_at']}",
                f"   Network    : {m['network']}",
                "",
            ]

            if cs:
                lines += [
                    "   Compression:",
                    f"     Original : {cs.get('total_original_bytes', '?'):,} bytes",
                    f"     Stored   : {cs.get('total_stored_bytes', '?'):,} bytes",
                    f"     Saved    : {cs.get('overall_saving_pct', '?')}%",
                    f"     Chunks compressed: {cs.get('chunks_compressed', '?')}/{m['total_chunks']}",
                    "",
                ]

            lines.append("   Chunk FileIDs on Hedera:")
            for chunk in m["chunks"]:
                i   = chunk.get("index", "?")
                fid = chunk["hedera_file_id"]
                comp = "z" if chunk.get("compressed") else " "
                if mode == "pdf":
                    pos = f"pages {chunk.get('page_start', '?')+1}–{chunk.get('page_end', '?')}"
                else:
                    pos = f"bytes {chunk.get('byte_start', '?'):,}–{chunk.get('byte_end', '?'):,}"
                lines.append(f"     [{i:02}] [{comp}] {pos}  →  {fid}")

            lines.append("\n   [z] = compressed chunk")

            self._info_box.configure(state="normal")
            self._info_box.delete("1.0", END)
            self._info_box.insert("1.0", "\n".join(lines))
            self._info_box.configure(state="disabled")

        except Exception as e:
            self._info_box.configure(state="normal")
            self._info_box.delete("1.0", END)
            self._info_box.insert("1.0", f"❌  Error: {e}")
            self._info_box.configure(state="disabled")


# ── Main App ──────────────────────────────────────────────────────────────────

class HashVaultApp(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("🔐 HashVault")
        self.geometry("640x700")
        self.minsize(580, 600)
        self.configure(fg_color=BG_DARK)

        # ── Title bar ─────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text="🔐  HashVault",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=20, weight="bold"),
                     text_color="#58a6ff").pack(side="left", padx=16)

        ctk.CTkLabel(header, text="Secure file storage on Hedera",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=FG_DIM).pack(side="left", padx=(0, 16))

        # ── Settings bar ──────────────────────────────────────────────────
        settings_bar = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=0, height=36)
        settings_bar.pack(fill="x", pady=(1, 0))
        settings_bar.pack_propagate(False)

        ctk.CTkLabel(settings_bar, text="Network:",
                     font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                     text_color=FG_DIM).pack(side="left", padx=(16, 4))

        self._network_var = ctk.StringVar(value="testnet")
        net_menu = ctk.CTkOptionMenu(settings_bar, variable=self._network_var,
                                     values=["testnet", "mainnet"], width=100,
                                     fg_color=BG_INPUT, button_color=ACCENT,
                                     button_hover_color="#388bfd",
                                     font=ctk.CTkFont(family=FONT_FAMILY, size=11))
        net_menu.pack(side="left", padx=(0, 16))

        self._mock_var = ctk.BooleanVar(
            value=os.getenv("HASHVAULT_MOCK", "").strip() in ("1", "true", "yes")
        )
        mock_cb = ctk.CTkCheckBox(settings_bar, text="Mock mode",
                                  variable=self._mock_var,
                                  font=ctk.CTkFont(family=FONT_FAMILY, size=12),
                                  text_color=FG_DIM, fg_color=ACCENT,
                                  hover_color="#388bfd", border_color=BORDER_CLR)
        mock_cb.pack(side="left")

        # ── Shared settings dict for tabs ─────────────────────────────────
        def _apply_mock():
            if self._mock_var.get():
                os.environ["HASHVAULT_MOCK"] = "1"
            else:
                os.environ.pop("HASHVAULT_MOCK", None)

        shared = {
            "network":    lambda: self._network_var.get(),
            "apply_mock": _apply_mock,
        }

        # ── Log area ──────────────────────────────────────────────────────
        self._log_box = ctk.CTkTextbox(self, height=120, state="disabled",
                                       fg_color=BG_INPUT, text_color=SUCCESS,
                                       border_color=BORDER_CLR, border_width=1,
                                       font=ctk.CTkFont(family="Courier New", size=11))
        self._log_box.pack(side="bottom", fill="x", padx=12, pady=(0, 10))

        log_label = ctk.CTkLabel(self, text="Log", anchor="w",
                                 font=ctk.CTkFont(family=FONT_FAMILY, size=11),
                                 text_color=FG_DIM)
        log_label.pack(side="bottom", anchor="w", padx=14, pady=(4, 0))

        log_writer = TextboxWriter(self._log_box)

        # ── Tabs ──────────────────────────────────────────────────────────
        tabview = ctk.CTkTabview(self, fg_color=BG_CARD, segmented_button_fg_color=BG_INPUT,
                                 segmented_button_selected_color=ACCENT,
                                 segmented_button_unselected_color=BG_INPUT,
                                 corner_radius=8)
        tabview.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        tab_store = tabview.add("Store")
        tab_fetch = tabview.add("Fetch")
        tab_info  = tabview.add("Info")

        StoreTab(tab_store, log_writer, shared).pack(fill="both", expand=True)
        FetchTab(tab_fetch, log_writer, shared).pack(fill="both", expand=True)
        InfoTab(tab_info).pack(fill="both", expand=True)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = HashVaultApp()
    app.mainloop()
