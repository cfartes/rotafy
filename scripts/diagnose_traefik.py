"""Run on the VPS: python3 scripts/diagnose_traefik.py.

Only prints networking and routing metadata, never environment or raw logs.
"""

import json
import subprocess


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True)


print("Docker:", docker("version", "--format", "{{.Server.Version}}").strip())
print("Compose:", docker("compose", "version", "--short").strip())
print("Swarm:", docker("info", "--format", "{{.Swarm.LocalNodeState}}").strip())
ids = docker("ps", "-q").split()
for identifier in ids:
    container = json.loads(docker("inspect", identifier))[0]
    config = container["Config"]
    labels = config.get("Labels") or {}
    routing = {
        key: value
        for key, value in labels.items()
        if key == "traefik.docker.network"
        or (
            key.startswith("traefik.http.routers.")
            and key.endswith((".entrypoints", ".tls.certresolver"))
        )
    }
    is_traefik = "traefik" in config["Image"].lower()
    if not is_traefik and not routing:
        continue
    result = {
        "name": container["Name"].lstrip("/"),
        "image": config["Image"],
        "networks": {
            name: data.get("IPAddress")
            for name, data in container["NetworkSettings"]["Networks"].items()
        },
        "ports": container["NetworkSettings"].get("Ports"),
        "routing": routing,
    }
    if is_traefik:
        result["safe_flags"] = [
            flag
            for flag in config.get("Cmd") or []
            if flag.lower().startswith(
                ("--entrypoints.", "--providers.docker", "--providers.swarm")
            )
            or (
                flag.lower().startswith("--certificatesresolvers.")
                and ".acme." in flag.lower()
            )
        ]
        # Filter out provider endpoints and ACME account/eab credentials.
        result["safe_flags"] = [
            flag
            for flag in result["safe_flags"]
            if not any(
                word in flag.lower()
                for word in (
                    "endpoint",
                    "email",
                    "eab",
                    "credential",
                    "secret",
                    "token",
                    "password",
                )
            )
        ]
        result["config_mounts"] = [
            mount["Destination"] for mount in container.get("Mounts", [])
        ]
    print(json.dumps(result, ensure_ascii=False, indent=2))
