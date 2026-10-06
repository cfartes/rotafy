"""Create/reuse the Nexus Android release identity without printing passwords."""

import os
import secrets
import shutil
import subprocess
from pathlib import Path

directory = Path.home() / ".nexus-rotafy" / "android-signing"
directory.mkdir(parents=True, exist_ok=True)
keystore = directory / "nexus-rotafy.jks"
credentials = directory / "key.properties"
if not keystore.exists() and not credentials.exists():
    password = secrets.token_hex(32)
    environment = dict(os.environ, ROTAFY_KEY_PASSWORD=password)
    keytool = shutil.which("keytool")
    if not keytool:
        raise SystemExit("Instale Java/keytool antes de gerar assinatura.")
    subprocess.run(
        [
            keytool,
            "-genkeypair",
            "-keystore",
            str(keystore),
            "-storetype",
            "JKS",
            "-alias",
            "rotafy",
            "-keyalg",
            "RSA",
            "-keysize",
            "3072",
            "-validity",
            "10000",
            "-dname",
            "CN=Nexus Rotafy, O=Nexus Data Analytics, C=BR",
            "-storepass:env",
            "ROTAFY_KEY_PASSWORD",
            "-keypass:env",
            "ROTAFY_KEY_PASSWORD",
        ],
        env=environment,
        check=True,
        capture_output=True,
    )
    credentials.write_text(
        f"storeFile={keystore.as_posix()}\nstorePassword={password}\nkeyPassword={password}\nkeyAlias=rotafy\n",
        encoding="utf-8",
    )
elif not keystore.exists() or not credentials.exists():
    raise SystemExit(
        "Assinatura incompleta. Recupere o arquivo ausente sem substituir a chave."
    )
target = (
    Path(__file__).resolve().parent.parent / "mobile" / "android" / "key.properties"
)
shutil.copyfile(credentials, target)
print("Assinatura configurada. Preserve em cofre os arquivos em:", directory)
