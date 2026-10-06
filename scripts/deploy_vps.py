#!/usr/bin/env python3
"""Instala o checkout Rotafy na VPS Linux, usando o Traefik existente."""

import argparse
import datetime
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "frotafy.nexusdataanalytics.tech"


def execute(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def output(args):
    return execute(args, text=True, capture_output=True, cwd=ROOT).stdout.strip()


def read_env(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key):
                raise ValueError(
                    "Formato inválido no ambiente; nenhuma credencial alterada."
                )
            if value.startswith('"'):
                value = json.loads(value)
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            values[key] = value
    return values


def write_env(path, values):
    if any(
        not isinstance(v, str) or any(c in v for c in "\n\r$") for v in values.values()
    ):
        raise ValueError("Ambiente não pode conter interpolação $ ou quebras de linha.")
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "x", encoding="utf-8") as stream:
        os.chmod(temporary, 0o600)
        stream.writelines(
            f"{key}={json.dumps(value, ensure_ascii=False)}\n"
            for key, value in values.items()
        )
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def choose(label, candidates, value, non_interactive):
    if value and value != "CHANGE_ME":
        return value
    candidates = sorted(set(candidates) - {""})
    if len(candidates) == 1:
        print(f"{label}: {candidates[0]}")
        return candidates[0]
    if non_interactive:
        raise ValueError(
            f"Informe {label}; detecção automática ambígua ou indisponível."
        )
    if candidates:
        print(f"Opções para {label}: {', '.join(candidates)}")
    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} é obrigatório.")
    return value


def routing(args, existing):
    ids = output(["docker", "ps", "-q"]).split()
    containers = json.loads(output(["docker", "inspect", *ids])) if ids else []
    proxies = [c for c in containers if "traefik" in c["Config"]["Image"].lower()]
    name = choose(
        "container Traefik",
        [c["Name"].lstrip("/") for c in proxies],
        args.traefik_container,
        args.non_interactive,
    )
    proxy = next((c for c in proxies if c["Name"].lstrip("/") == name), None)
    if proxy is None:
        raise ValueError("Traefik informado não está em execução.")
    flags = proxy["Config"].get("Cmd") or []
    if any(f.lower() == "--providers.docker.swarmmode=true" for f in flags):
        raise ValueError(
            "Swarm mode detectado; instalador exige Compose/provider Docker."
        )
    if any(f.lower() == "--providers.docker=false" for f in flags):
        raise ValueError("Provider Docker desabilitado no Traefik.")
    if any(
        f.lower().startswith("--providers.swarm") and not f.lower().endswith("=false")
        for f in flags
    ):
        raise ValueError(
            "Provider Swarm detectado. Instalador exige Docker Compose/provider Docker."
        )
    networks = proxy["NetworkSettings"]["Networks"]
    network = choose(
        "rede Traefik",
        networks,
        args.network or existing.get("TRAEFIK_NETWORK"),
        args.non_interactive,
    )
    if network not in networks:
        raise ValueError("Traefik não pertence à rede informada.")
    metadata = json.loads(output(["docker", "network", "inspect", network]))[0]
    if metadata.get("Driver") != "bridge" or metadata.get("Internal"):
        raise ValueError(
            "A rede Traefik deve ser uma bridge externa com saída de rede."
        )
    entries, resolvers = set(), set()
    for container in containers:
        labels = container["Config"].get("Labels") or {}
        for key, value in labels.items():
            if key.startswith("traefik.http.routers.") and key.endswith(
                ".tls.certresolver"
            ):
                resolvers.add(value)
                entries.update(
                    labels.get(
                        key.removesuffix(".tls.certresolver") + ".entrypoints", ""
                    ).split(",")
                )
    for flag in flags:
        match = re.match(r"--certificatesresolvers\.([^.]+)\.", flag, re.IGNORECASE)
        if match:
            resolvers.add(match[1])
        match = re.match(
            r"--entrypoints\.([^.]+)\.address=.*:443(?:/tcp)?$", flag, re.IGNORECASE
        )
        if match:
            entries.add(match[1])
    entry = choose(
        "entrypoint HTTPS",
        entries,
        args.entrypoint or existing.get("TRAEFIK_HTTPS_ENTRYPOINT"),
        args.non_interactive,
    )
    resolver = choose(
        "resolver TLS",
        resolvers,
        args.resolver or existing.get("TRAEFIK_CERTRESOLVER"),
        args.non_interactive,
    )
    for value in (network, entry, resolver):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Nome de rede/entrypoint/resolver inválido.")
    address = networks[network].get("IPAddress")
    if not address:
        raise ValueError("Traefik sem IP disponível na rede escolhida.")
    return {
        "TRAEFIK_NETWORK": network,
        "TRAEFIK_HTTPS_ENTRYPOINT": entry,
        "TRAEFIK_CERTRESOLVER": resolver,
        "TRAEFIK_TRUSTED_IPS": address,
    }


def deploy(args):
    if sys.platform != "linux":
        raise ValueError(
            "Execute na VPS Linux com Python 3.9+, Git, Docker e Compose v2."
        )
    os.umask(0o077)
    output(["docker", "info"])
    output(["docker", "compose", "version"])
    if output(["git", "status", "--porcelain"]):
        raise ValueError("Checkout com alterações. Publique uma revisão Git limpa.")
    path = ROOT / ".env.production"
    existing = read_env(path)
    volume_exists = (
        subprocess.run(
            ["docker", "volume", "inspect", "nexus-rotafy-prod_database"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )
    if volume_exists and not existing:
        raise ValueError(
            "Banco existente sem .env.production. Recupere as credenciais originais; nenhuma senha nova foi gerada."
        )
    values = read_env(ROOT / ".env.production.example")
    values.update(existing)
    values.update(routing(args, existing))
    if not existing:
        for key in (
            "POSTGRES_PASSWORD",
            "APP_DB_PASSWORD",
            "PLATFORM_DB_PASSWORD",
            "BOOTSTRAP_PASSWORD",
        ):
            values[key] = secrets.token_hex(32)
    for key in ("POSTGRES_PASSWORD", "APP_DB_PASSWORD", "PLATFORM_DB_PASSWORD"):
        if not re.fullmatch(r"[0-9a-fA-F]{64}", values.get(key, "")):
            raise ValueError(
                f"{key} exige 64 caracteres hexadecimais; credenciais existentes não serão regeneradas."
            )
    if len(values.get("BOOTSTRAP_PASSWORD", "")) < 12 or values[
        "BOOTSTRAP_PASSWORD"
    ].startswith("CHANGE_ME"):
        raise ValueError("Configure senha Nexus válida no ambiente existente.")
    if args.admin_email:
        values["BOOTSTRAP_EMAIL"] = args.admin_email
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values.get("BOOTSTRAP_EMAIL", "")):
        raise ValueError("E-mail Nexus inválido.")
    values["RELEASE"] = "git-" + output(["git", "rev-parse", "--short=12", "HEAD"])
    if args.dry_run:
        print(
            "Pré-verificação concluída, sem alterar arquivos/containers. Entrega:",
            values["RELEASE"],
        )
        return
    write_env(path, values)
    compose = [
        "docker",
        "compose",
        "--project-name",
        "nexus-rotafy-prod",
        "--env-file",
        str(path),
        "-f",
        str(ROOT / "compose.production.yaml"),
    ]
    environment = {k: v for k, v in os.environ.items() if k not in values}

    def run(*parameters, **kwargs):
        return execute([*compose, *parameters], cwd=ROOT, env=environment, **kwargs)

    run("config", "--quiet")
    run("build", "api", "web")
    if volume_exists:
        print("Banco existente: backup obrigatório antes das migrações.")
        run("up", "-d", "--wait", "--wait-timeout", "120", "db")
        directory = ROOT / "artifacts" / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        filename = (
            datetime.datetime.now(datetime.timezone.utc).strftime(
                "predeploy-%Y%m%dT%H%M%SZ-"
            )
            + secrets.token_hex(4)
            + ".dump"
        )
        backup = directory / filename
        with open(backup, "xb") as stream:
            result = subprocess.run(
                [
                    *compose,
                    "exec",
                    "-T",
                    "db",
                    "pg_dump",
                    "-U",
                    "rotafy_owner",
                    "-d",
                    "rotafy",
                    "-Fc",
                ],
                cwd=ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.PIPE,
                check=False,
            )
        with open(backup, "rb") as stream:
            valid = stream.read(5) == b"PGDMP"
        if result.returncode or not valid:
            raise ValueError(
                "Backup falhou; migrações não iniciadas. Arquivo incompleto não deve ser utilizado."
            )
        print(
            "Backup local:", backup, "(mantenha também backup externo criptografado)."
        )
    run("up", "-d", "--wait", "--wait-timeout", "300")
    for service in ("migrate", "bootstrap"):
        identifier = run(
            "ps", "-aq", service, text=True, capture_output=True
        ).stdout.strip()
        state = (
            json.loads(output(["docker", "inspect", identifier]))[0]["State"]
            if identifier
            else {}
        )
        if state.get("Status") != "exited" or state.get("ExitCode") != 0:
            raise ValueError(f"{service} não concluiu com sucesso.")
    run(
        "exec",
        "-T",
        "api",
        "python",
        "-c",
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')",
    )
    run("ps")
    print("Verificando DNS, certificado e rota pública HTTPS...")
    for attempt in range(12):
        try:
            with urllib.request.urlopen(
                f"https://{DOMAIN}/api/v1/health", timeout=10
            ) as response:
                if response.status == 200 and json.load(response).get("status") == "ok":
                    break
                raise ValueError("Resposta pública não corresponde ao health da API.")
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            AttributeError,
        ):
            if attempt == 11:
                raise ValueError(
                    "Serviços iniciados, mas HTTPS público indisponível. Confira DNS e Traefik. Sem rollback automático."
                ) from None
            time.sleep(5)
    print(f"Publicado: https://{DOMAIN}")
    print(
        "Credenciais Nexus: BOOTSTRAP_EMAIL/BOOTSTRAP_PASSWORD em .env.production; não compartilhe esse arquivo."
    )
    print(
        "Configure Resend e storage de backups externos conforme docs/IMPLANTACAO_E_OPERACAO.md."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "network",
        "entrypoint",
        "resolver",
        "traefik-container",
        "admin-email",
    ):
        parser.add_argument("--" + name)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.dry_run:
            deploy(args)
        else:
            import fcntl

            with open(ROOT / ".deploy.lock", "a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError("Outra implantação em execução.") from None
                deploy(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "Falha de comando/arquivo. Implantação interrompida; verifique serviços sem compartilhar segredos."
        )
        print("ERRO:", message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
