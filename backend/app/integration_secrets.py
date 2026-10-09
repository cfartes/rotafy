"""Chave local persistente, separada do banco e nunca devolvida pela API."""

import os
from pathlib import Path

from cryptography.fernet import Fernet


def key_path():
    return Path(os.environ.get("INTEGRATION_KEY_FILE", "/run/rotafy/integrations.key"))


def encrypt(value: str) -> str:
    return (
        Fernet(key_path().read_bytes().strip()).encrypt(value.encode()).decode()
        if value
        else ""
    )


def decrypt(value: str) -> str:
    return (
        Fernet(key_path().read_bytes().strip()).decrypt(value.encode()).decode()
        if value
        else ""
    )


def initialize():
    path = key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o750)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        Fernet(path.read_bytes().strip())
    else:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(Fernet.generate_key())
    if os.getuid() == 0:
        import pwd

        account = pwd.getpwnam("rotafy")
        os.chown(path.parent, account.pw_uid, account.pw_gid)
        os.chown(path, account.pw_uid, account.pw_gid)
    os.chmod(path, 0o600)
    print("Proteção das integrações pronta; chave preservada no volume persistente.")


if __name__ == "__main__":
    initialize()
