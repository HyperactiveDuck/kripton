"""
vault/hedera_client.py — Hedera File Service via REST API (no SDK required).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MOCK MODE (for local testing — no credentials needed):
  export HASHVAULT_MOCK=1
  python cli.py store myfile.pdf -p mypassword

REAL MODE (testnet — free account at portal.hedera.com):
  export HEDERA_ACCOUNT_ID=0.0.XXXXXX
  export HEDERA_PRIVATE_KEY=302e...
  python cli.py store myfile.pdf -p mypassword
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os


def _use_mock() -> bool:
    return os.getenv("HASHVAULT_MOCK", "").strip() in ("1", "true", "yes")


def upload_bytes(data: bytes, memo: str = "", network: str = "testnet") -> str:
    if _use_mock():
        from vault.hedera_client_mock import upload_bytes as _upload
        return _upload(data, memo, network)
    return _real_upload(data, memo, network)


def download_bytes(file_id_str: str, network: str = "testnet") -> bytes:
    if _use_mock():
        from vault.hedera_client_mock import download_bytes as _download
        return _download(file_id_str, network)
    return _real_download(file_id_str, network)


def delete_file(file_id_str: str, network: str = "testnet") -> None:
    if _use_mock():
        from vault.hedera_client_mock import delete_file as _delete
        _delete(file_id_str, network)
        return
    _real_delete(file_id_str, network)


def _get_sdk():
    try:
        import hedera
        return hedera
    except ImportError:
        raise ImportError(
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Hedera SDK not installed.\n\n"
            "For LOCAL TESTING (no account needed):\n"
            "  export HASHVAULT_MOCK=1\n\n"
            "For REAL HEDERA (testnet/mainnet):\n"
            "  pip install hedera-sdk-python\n"
            "  export HEDERA_ACCOUNT_ID=0.0.XXXXXX\n"
            "  export HEDERA_PRIVATE_KEY=302e...\n"
            "  Get a free account at: https://portal.hedera.com/\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )


def _get_credentials():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    account_id  = os.getenv("HEDERA_ACCOUNT_ID")
    private_key = os.getenv("HEDERA_PRIVATE_KEY")

    if not account_id or not private_key:
        raise RuntimeError(
            "\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Missing Hedera credentials.\n\n"
            "  export HEDERA_ACCOUNT_ID=0.0.XXXXXX\n"
            "  export HEDERA_PRIVATE_KEY=302e...\n\n"
            "Or use mock mode:\n"
            "  export HASHVAULT_MOCK=1\n\n"
            "Get a free account at: https://portal.hedera.com/\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        )
    return account_id, private_key


def _build_client(network: str):
    hedera = _get_sdk()
    account_id, private_key = _get_credentials()
    client = (hedera.Client.forMainnet() if network == "mainnet"
              else hedera.Client.forTestnet())
    client.setOperator(
        hedera.AccountId.fromString(account_id),
        hedera.PrivateKey.fromString(private_key),
    )
    return client


def _real_upload(data: bytes, memo: str, network: str) -> str:
    hedera = _get_sdk()
    client = _build_client(network)
    CHUNK  = 1024

    tx = (
        hedera.FileCreateTransaction()
        .setKeys(client.getOperatorPublicKey())
        .setContents(data[:CHUNK])
        .setFileMemo(memo)
        .freezeWith(client)
        .sign(client.getOperatorKey())
    )
    file_id = tx.execute(client).getReceipt(client).fileId

    offset = CHUNK
    while offset < len(data):
        piece = data[offset : offset + CHUNK]
        (
            hedera.FileAppendTransaction()
            .setFileId(file_id)
            .setContents(piece)
            .freezeWith(client)
            .sign(client.getOperatorKey())
            .execute(client)
            .getReceipt(client)
        )
        offset += CHUNK

    return str(file_id)


def _real_download(file_id_str: str, network: str) -> bytes:
    hedera  = _get_sdk()
    client  = _build_client(network)
    file_id = hedera.FileId.fromString(file_id_str)
    return bytes(hedera.FileContentsQuery().setFileId(file_id).execute(client))


def _real_delete(file_id_str: str, network: str) -> None:
    hedera  = _get_sdk()
    client  = _build_client(network)
    file_id = hedera.FileId.fromString(file_id_str)
    (
        hedera.FileDeleteTransaction()
        .setFileId(file_id)
        .freezeWith(client)
        .sign(client.getOperatorKey())
        .execute(client)
        .getReceipt(client)
    )
