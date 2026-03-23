# Work in progress, You files will infact get lost, break etc. A lot of planned security, storage and compression logic is missing atm. Just a working demo.

# 🔐 Kripton (HashVault)

**Split, compress, encrypt, and store any file on the Hedera Hashgraph network.**

Each chunk is independently compressed, encrypted with **AES-256-GCM**, and uploaded as a separate file on the **Hedera File Service**. A local manifest JSON is all you need to retrieve and reconstruct the original.

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Any file type** | PDF-aware splitting (by page) or raw byte splitting for images, videos, archives — anything |
| **AES-256-GCM encryption** | Authenticated encryption with unique salt + IV per chunk |
| **PBKDF2 key derivation** | 600,000 iterations (NIST SP 800-132), brute-force resistant |
| **Smart compression** | zlib compression per chunk — automatically skipped if it doesn't save ≥5% |
| **Tamper detection** | GCM authentication tag catches any corruption or modification |
| **CLI + Desktop GUI** | Full CLI via Click, plus a CustomTkinter desktop app with pipeline status |
| **Mock mode** | Test the full pipeline locally without a Hedera account or network access |
| **Hedera testnet & mainnet** | Switch between networks with a flag |

---

## 🏗️ Architecture

```
STORE:  File ──► split into N chunks ──► zlib compress (if beneficial)
             ──► AES-256-GCM encrypt (unique salt + IV per chunk)
             ──► upload to Hedera File Service
             ──► save manifest.json

FETCH:  manifest.json ──► download chunks from Hedera
                       ──► decrypt (AES-256-GCM)
                       ──► decompress (if was compressed)
                       ──► reassemble ──► original file
```

The manifest contains **no keys** and **no plaintext** — only Hedera FileIds, chunk positions, and compression metadata. Losing the manifest or forgetting the password means the file **cannot** be recovered.

---

## 📁 Project Structure

```
kripton/
├── cli.py                      # Click CLI entry point (store / fetch / info)
├── gui.py                      # CustomTkinter desktop GUI
└── vault/
    ├── crypto.py               # AES-256-GCM encrypt/decrypt + zlib compression
    ├── store.py                # Store pipeline (split → compress → encrypt → upload)
    ├── fetch.py                # Fetch pipeline (download → decrypt → decompress → reassemble)
    ├── manifest.py             # Manifest build / save / load
    ├── hedera_client.py        # Hedera File Service client (routes to real or mock)
    └── hedera_client_mock.py   # Local filesystem mock for testing
```

---

## 🚀 Getting Started

### 1. Clone & install

```bash
git clone https://github.com/HyperactiveDuck/kripton
cd kripton
python -m venv .venv
source .venv/bin/activate
pip install pypdf cryptography click customtkinter
```

### 2. Quick test (mock mode — no Hedera account needed)

```bash
export HASHVAULT_MOCK=1

# Store a file
python cli.py store myfile.png --password "s3cret"

# Fetch it back
python cli.py fetch myfile.manifest.json --password "s3cret"

# Inspect the manifest
python cli.py info myfile.manifest.json
```

### 3. Use with real Hedera (testnet)

1. Create a free account at [portal.hedera.com](https://portal.hedera.com/)
2. Set your credentials:

```bash
export HEDERA_ACCOUNT_ID=0.0.1234567
export HEDERA_PRIVATE_KEY=302e...
pip install hedera-sdk-python
```

3. Run normally (no `HASHVAULT_MOCK`):

```bash
python cli.py store document.pdf --password "mypassword" --network testnet
```

---

## 🖥️ Desktop GUI

Launch the graphical interface:

```bash
HASHVAULT_MOCK=1 python gui.py
```

The GUI provides:
- **Store tab** — file picker, password, mode/chunk-size options, compression preview
- **Fetch tab** — manifest picker, password, output path
- **Info tab** — manifest inspector
- **Pipeline status** — real-time step-by-step progress (Split → Compress → Encrypt → Upload → Manifest)
- **Settings bar** — network selector + mock mode toggle
- **Log panel** — full pipeline output

---

## ⌨️ CLI Reference

### `store` — Encrypt and upload a file

```bash
python cli.py store <file> [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--password` / `-p` | prompted | Encryption password |
| `--mode` / `-m` | `auto` | Split mode: `auto`, `pdf`, or `raw` |
| `--chunk-size` / `-c` | `5` | Pages per chunk (pdf) or KB per chunk (raw) |
| `--manifest` | `<file>.manifest.json` | Custom manifest output path |
| `--network` | `testnet` | `testnet` or `mainnet` |

### `fetch` — Download and reconstruct a file

```bash
python cli.py fetch <manifest.json> [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--password` / `-p` | prompted | Decryption password |
| `--out` / `-o` | `reconstructed_<name>` | Output file path |
| `--network` | `testnet` | `testnet` or `mainnet` |

### `info` — Inspect a manifest (no password needed)

```bash
python cli.py info <manifest.json>
```

---

## 🔒 Encryption Details

| Property | Value |
|----------|-------|
| Algorithm | AES-256-GCM |
| Key derivation | PBKDF2-HMAC-SHA256 |
| KDF iterations | 600,000 (NIST SP 800-132) |
| Salt | 16 bytes random, unique per chunk |
| IV / Nonce | 12 bytes random, unique per chunk |
| Compression | zlib level 6, skipped if <5% savings |
| Authenticated | ✅ GCM tag detects tampering |

### Wire format (per chunk)

```
[ flag (1 byte) ][ salt (16 bytes) ][ IV (12 bytes) ][ ciphertext + GCM tag ]

flag: 0x01 = compressed before encrypting
      0x00 = raw (not compressed)
```

---

## 🧪 Mock Mode

Set `HASHVAULT_MOCK=1` to test without a Hedera account. The mock:

- Stores encrypted blobs in `~/.hashvault_store/<file_id>.bin`
- Generates fake FileIds (`0.0.5000000`, `0.0.5000001`, …)
- Tracks state in `~/.hashvault_store/index.json`
- Is a **drop-in replacement** — same API, same behavior, local filesystem only

```bash
export HASHVAULT_MOCK=1
python cli.py store photo.jpg -p test123
python cli.py fetch photo.manifest.json -p test123
# ✅ Works entirely offline
```

---

## 📋 Manifest Format

```json
{
  "version": "2.0",
  "original_filename": "photo.png",
  "mode": "raw",
  "total_size": 36661,
  "total_chunks": 1,
  "chunk_size": 100,
  "network": "testnet",
  "created_at": "2026-03-23T23:02:04.934340+00:00",
  "compression_stats": {
    "total_original_bytes": 36661,
    "total_stored_bytes": 36706,
    "overall_saving_pct": -0.1,
    "chunks_compressed": 0
  },
  "chunks": [
    {
      "index": 0,
      "hedera_file_id": "0.0.5000003",
      "original_bytes": 36661,
      "stored_bytes": 36706,
      "compressed": false,
      "byte_start": 0,
      "byte_end": 36661
    }
  ]
}
```

> ⚠️ **Keep your manifest file safe.** Without it (and your password), the encrypted chunks on Hedera cannot be reassembled.

---

## 🔮 Roadmap

- [ ] Upload encrypted manifest to Hedera (single FileId + password = full recovery)
- [ ] Hedera Consensus Service (HCS) for on-chain metadata logging
- [ ] Web interface (FastAPI backend)
- [ ] Multi-file batch processing
- [ ] Shamir's Secret Sharing for the password

---

## 🛠️ Requirements

- Python 3.10+
- `pypdf` — PDF splitting and merging
- `cryptography` — AES-256-GCM + PBKDF2
- `click` — CLI framework
- `customtkinter` — Desktop GUI
- `hedera-sdk-python` — *(optional, only for real Hedera network)*

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
