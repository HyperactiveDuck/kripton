# HashVault 🔐

**Split, encrypt, and store PDF chunks on Hedera Hashgraph.**  
Each chunk is independently encrypted with AES-256-GCM and stored as a  
separate file on the Hedera File Service. A local manifest JSON is all  
you need to retrieve and reconstruct the original PDF.

---

## Architecture

```
STORE:  PDF ──► split into N chunks ──► AES-256-GCM encrypt (unique IV per chunk)
                ──► upload to Hedera File Service ──► save manifest.json

FETCH:  manifest.json ──► download FileIds from Hedera
                       ──► decrypt each chunk
                       ──► merge pages ──► reconstructed PDF
```

---

## Setup

### 1. Install dependencies

```bash
pip install pypdf cryptography click hedera-sdk-python python-dotenv
```

### 2. Get a Hedera testnet account (free)

1. Go to https://portal.hedera.com/
2. Create an account → grab your **Account ID** and **Private Key**
3. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
# edit .env
HEDERA_ACCOUNT_ID=0.0.1234567
HEDERA_PRIVATE_KEY=302e...
```

---

## Usage

### Store a PDF

```bash
python cli.py store my_document.pdf --password "s3cret" --chunk-size 5
```

Options:
| Flag | Default | Description |
|------|---------|-------------|
| `--password` / `-p` | prompted | Encryption password |
| `--chunk-size` / `-c` | `5` | Pages per chunk |
| `--manifest` / `-m` | `<pdf>.manifest.json` | Output manifest path |
| `--network` | `testnet` | `testnet` or `mainnet` |

### Fetch (reconstruct) a PDF

```bash
python cli.py fetch my_document.manifest.json --password "s3cret"
```

Outputs `reconstructed_my_document.pdf` in the current directory.

### Inspect a manifest

```bash
python cli.py info my_document.manifest.json
```

---

## Encryption Details

| Property | Value |
|----------|-------|
| Algorithm | AES-256-GCM |
| Key derivation | PBKDF2-HMAC-SHA256 |
| KDF iterations | 600,000 (NIST SP 800-132) |
| Salt | 16 bytes random, unique per chunk |
| IV/Nonce | 12 bytes random, unique per chunk |
| Authenticated |  GCM tag detects tampering |

The manifest contains **no keys** and **no plaintext** — only Hedera FileIds  
and page metadata. Losing the manifest or forgetting the password means the  
file cannot be recovered.

---

## Project Structure

```
hashvault/
├── cli.py                  # Click CLI entry point
├── vault/
│   ├── crypto.py           # AES-256-GCM encrypt/decrypt
│   ├── hedera_client.py    # Hedera File Service upload/download
│   ├── manifest.py         # Manifest build/save/load
│   ├── store.py            # Store pipeline
│   └── fetch.py            # Fetch pipeline
├── .env.example
└── README.md
```

---

## Migrating to a Web App

The CLI functions (`store_pdf`, `fetch_pdf`) are pure Python with no CLI  
dependencies. Wrap them in FastAPI endpoints:

```python
from fastapi import FastAPI, UploadFile
from vault.store import store_pdf
from vault.fetch import fetch_pdf

app = FastAPI()

@app.post("/store")
async def store(file: UploadFile, password: str):
    # save upload to temp path, call store_pdf(...)
    ...

@app.post("/fetch")
async def fetch(manifest: UploadFile, password: str):
    # call fetch_pdf(...)
    ...
```
