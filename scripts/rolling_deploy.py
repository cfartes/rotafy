"""Two application slots behind a stable gateway; the database is never replaced."""

import copy
import ipaddress
import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

WORKERS = ("billing", "email", "geocoding", "whatsapp")
DRAIN_SECONDS = 300


def stage_assets(output, images, volume):
    images = list(dict.fromkeys(images))
    for image in images:
        # BusyBox cp -n skips an existing destination directory, including its
        # children. Merge instead; hash-named bundles are safe to overwrite.
        output(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "-v",
                volume + ":/assets",
                "--entrypoint",
                "sh",
                image,
                "-c",
                "cp -a /usr/share/nginx/html/assets/. /assets/",
            ]
        )
    for image in images:
        output(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--user",
                "nginx",
                "-v",
                volume + ":/assets:ro",
                "--entrypoint",
                "sh",
                image,
                "-c",
                'find /usr/share/nginx/html/assets -type f | while IFS= read -r file; do cmp -s "$file" "/assets/${file#/usr/share/nginx/html/assets/}" || exit 1; done',
            ]
        )


def verify_public_assets(base):
    with urllib.request.urlopen(base + "/", timeout=10) as response:
        markup = response.read().decode("utf-8")
    paths = list(
        dict.fromkeys(re.findall(r"""(?:src|href)=["'](/assets/[^"']+)["']""", markup))
    )
    if not all(
        any(path.endswith(extension) for path in paths) for extension in (".js", ".css")
    ):
        raise ValueError("A página pública não identifica seu JavaScript/CSS.")
    for path in paths:
        expected = (
            ("application/javascript", "text/javascript")
            if path.endswith(".js")
            else ("text/css",)
            if path.endswith(".css")
            else None
        )
        if expected:
            with urllib.request.urlopen(base + path, timeout=10) as response:
                if (
                    response.status != 200
                    or response.headers.get_content_type() not in expected
                    or not response.read(1)
                ):
                    raise ValueError(
                        "JavaScript/CSS público indisponível ou com tipo incorreto."
                    )


def save(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def slot_config(base, project, slot, directory):
    config = {
        "services": {},
        "networks": {
            "database": {
                "external": True,
                "name": base["networks"]["database"]["name"],
            },
            "frontend": {
                "external": True,
                "name": base["networks"]["frontend"]["name"],
            },
            "email_egress": {},
        },
        "volumes": {},
    }
    subnet = base["x-deploy-subnet"]
    alias = f"{project}-{slot}-api"
    for name in ("api", "web", *WORKERS):
        service = copy.deepcopy(base["services"][name])
        for key in ("build", "depends_on", "profiles", "container_name"):
            service.pop(key, None)
        service["labels"] = {"traefik.enable": "false"}
        if name == "api":
            service["command"][-1] = subnet
            service["networks"] = {
                "database": {},
                "frontend": {"aliases": [alias]},
                "email_egress": {},
            }
        elif name == "web":
            service["networks"] = {"frontend": {"aliases": [f"{project}-{slot}-web"]}}
            service["volumes"] = [
                {
                    "type": "bind",
                    "source": str(directory / "web.conf"),
                    "target": "/etc/nginx/conf.d/default.conf",
                    "read_only": True,
                }
            ]
            service["healthcheck"] = {
                "test": [
                    "CMD",
                    "wget",
                    "-q",
                    "-O",
                    "/dev/null",
                    "http://127.0.0.1/version.json",
                ],
                "interval": "5s",
                "timeout": "5s",
                "retries": 20,
            }
        else:
            service["networks"] = {"database": {}, "email_egress": {}}
        for volume in service.get("volumes", []):
            if volume["type"] == "volume":
                source = volume["source"]
                config["volumes"][source] = {
                    "external": True,
                    "name": base["volumes"][source]["name"],
                }
        config["services"][name] = service
    return config


def gateway_config(api, web, trusted):
    # Only the existing Traefik can supply the original client's address.
    ipaddress.ip_address(trusted)
    return f"""resolver 127.0.0.11 valid=5s ipv6=off;
upstream rotafy_api {{ zone rotafy_api 64k; server {api}:8000 resolve; }}
upstream rotafy_web {{ zone rotafy_web 64k; server {web}:80 resolve; }}
server {{
    listen 80;
    access_log off;
    # Upstream error logs otherwise include private ticket URLs.
    error_log /dev/stderr crit;
    client_max_body_size 3m;
    set_real_ip_from {trusted};
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto https;
    proxy_read_timeout 180s;
    proxy_send_timeout 180s;
    location ^~ /assets/ {{ root /srv; try_files $uri =404; add_header Cache-Control "public, max-age=31536000, immutable"; add_header X-Content-Type-Options nosniff always; }}
    location /api/ {{ proxy_pass http://rotafy_api; }}
    location = /api/v1/nexus/mobile-release {{ client_max_body_size 150m; proxy_pass http://rotafy_api; }}
    location / {{ proxy_pass http://rotafy_web; }}
}}
"""


class RollingDeployment:
    def __init__(self, root, project, run, output, values):
        self.root, self.project = root, project
        self.run, self.output, self.values = run, output, values
        self.directory = root / "artifacts" / "deploy"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_path = self.directory / "state.json"
        self.gateway = self.directory / "gateway"
        self.gateway.mkdir(exist_ok=True)
        self.state = (
            json.loads(self.state_path.read_text())
            if self.state_path.exists()
            else None
        )

    def compose(self, target, *args):
        return subprocess.run(
            [
                "docker",
                "compose",
                "--project-name",
                target["project"],
                "-f",
                target["compose"],
                *args,
            ],
            check=True,
            cwd=self.root,
            capture_output=True,
            text=True,
        )

    def edge(self, *args):
        return self.compose(
            {
                "project": self.project + "-edge",
                "compose": str(self.gateway / "compose.json"),
            },
            *args,
        )

    def stopped(self, target):
        ids = self.compose(
            target, "ps", "--status", "running", "-q", *WORKERS
        ).stdout.split()
        if target["slot"] == "legacy" and ids:
            self.stop_legacy(target, ids)
            return
        self.compose(target, "stop", "--timeout", str(DRAIN_SECONDS), *WORKERS)
        if ids:
            states = json.loads(self.output(["docker", "inspect", *ids]))
            if any(
                c["State"].get("Running") or c["State"].get("ExitCode") == 137
                for c in states
            ):
                raise ValueError(
                    "Worker não terminou no prazo; confira envios incertos antes de tentar novamente."
                )

    def stop_legacy(self, target, ids):
        # Old PID-1 workers have no drain handler. Freeze claims and verify
        # that no transaction or committed external send is still in flight.
        config = json.loads(Path(target["compose"]).read_text())
        network = config["networks"]["database"]["name"]
        containers = json.loads(self.output(["docker", "inspect", *ids]))
        addresses = [
            str(ipaddress.ip_address(c["NetworkSettings"]["Networks"][network][field]))
            for c in containers
            for field in ("IPAddress", "GlobalIPv6Address")
            if c["NetworkSettings"]["Networks"][network].get(field)
        ]
        quoted = ",".join("'" + address + "'" for address in addresses)
        checks = [
            f"(SELECT count(*) FROM pg_stat_activity WHERE client_addr::text IN ({quoted}) AND xact_start IS NOT NULL)"
        ]
        for table, status in (
            ("whatsapp_outbox", "sending"),
            ("whatsapp_chat_outbox", "sending"),
            ("whatsapp_automation_outbox", "sending"),
            ("billing_notifications", "sending"),
            ("nps_messages", "sending"),
            ("billing_checkouts", "creating"),
            ("billing_payment_events", "verifying"),
        ):
            checks.append(f"(SELECT count(*) FROM {table} WHERE status='{status}')")
        deadline = time.monotonic() + DRAIN_SECONDS
        while time.monotonic() < deadline:
            killed = False
            try:
                self.output(["docker", "pause", *ids])
                result = self.run(
                    "exec",
                    "-T",
                    "-e",
                    "PGOPTIONS=-c statement_timeout=3000",
                    "db",
                    "psql",
                    "-XAt",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    "rotafy_owner",
                    "-d",
                    "rotafy",
                    "-c",
                    "SELECT " + "+".join(checks),
                    text=True,
                    capture_output=True,
                )
                if int(result.stdout.strip()) == 0:
                    self.output(["docker", "kill", *ids])
                    killed = True
                    return
            finally:
                if not killed:
                    self.resume_legacy(target)
            time.sleep(1)
        raise ValueError(
            "Workers antigos ocupados; tentativa cancelada e filas retomadas. Tente em horário de menor movimento."
        )

    def resume_legacy(self, target):
        ids = self.compose(target, "ps", "-aq", *WORKERS).stdout.split()
        if ids:
            containers = json.loads(self.output(["docker", "inspect", *ids]))
            paused = [c["Id"] for c in containers if c["State"].get("Paused")]
            if paused:
                self.output(["docker", "unpause", *paused])

    def start_workers(self, target, reuse=False):
        self.compose(
            target,
            "up",
            "-d",
            "--no-deps",
            *(["--no-recreate"] if reuse else []),
            "--wait",
            "--wait-timeout",
            "300",
            *WORKERS,
        )

    def route(self, target):
        if target["slot"] == "legacy":
            self.edge("stop", "gateway")
            return
        path = self.gateway / "active.conf"
        prior = path.read_text() if path.exists() else None
        text = gateway_config(
            f"{self.project}-{target['slot']}-api",
            f"{self.project}-{target['slot']}-web",
            self.values["TRAEFIK_TRUSTED_IPS"],
        )
        temporary = path.with_suffix(".tmp")
        temporary.write_text(text)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        try:
            running = self.edge("ps", "-q", "gateway").stdout.strip()
            if running:
                self.edge("exec", "-T", "gateway", "nginx", "-t")
                self.edge("exec", "-T", "gateway", "nginx", "-s", "reload")
            else:
                self.edge("up", "-d", "--wait", "--wait-timeout", "120", "gateway")
            self.verify(target)
        except Exception:
            if prior is not None:
                temporary.write_text(prior)
                os.chmod(temporary, 0o644)
                os.replace(temporary, path)
            raise

    def verify(self, target):
        expected = target["release"]
        for attempt in range(18):
            try:
                for path in ("/version.json", "/api/v1/health"):
                    with urllib.request.urlopen(
                        f"https://rotafy.nexusdataanalytics.tech{path}?deploy={time.time_ns()}",
                        timeout=10,
                    ) as response:
                        body = json.load(response)
                    if body.get("release", body.get("version")) != expected:
                        raise ValueError(
                            "Public endpoint still serves another release."
                        )
            except (OSError, ValueError):
                if attempt == 17:
                    raise ValueError(
                        "Nova versão não confirmada via HTTPS; retornando à anterior."
                    ) from None
                time.sleep(2)
            else:
                try:
                    verify_public_assets("https://rotafy.nexusdataanalytics.tech")
                except OSError:
                    raise ValueError(
                        "Arquivos públicos JavaScript/CSS não acessíveis; publicação cancelada."
                    ) from None
                return

    def restore(self, old, candidate):
        # Stop new senders before restarting old ones, even after a partial failure.
        try:
            self.stopped(candidate)
        finally:
            self.route(old)
        if old["slot"] == "legacy":
            self.resume_legacy(old)
        self.start_workers(old, reuse=True)
        self.state = {
            "active": old,
            "previous": None,
            "phase": "ready",
            "changed_at": time.time(),
        }
        save(self.state_path, self.state)

    def recover(self):
        if self.state and self.state.get("phase") != "ready":
            self.restore(self.state["active"], self.state["candidate"])
            raise ValueError(
                "Atualização interrompida recuperada; versão anterior ativa. Execute novamente após conferir os serviços."
            )

    def preflight(self):
        if self.state and time.time() - self.state["changed_at"] < DRAIN_SECONDS:
            raise ValueError(
                "Aguarde 5 minutos após a última troca antes de reutilizar uma versão."
            )
        if shutil.disk_usage(self.root).free < 3 * 1024**3:
            raise ValueError(
                "Reserve ao menos 3 GiB livres para preparar a atualização."
            )
        memory = Path("/proc/meminfo")
        if memory.exists():
            available = next(
                int(line.split()[1])
                for line in memory.read_text().splitlines()
                if line.startswith("MemAvailable:")
            )
            if available < 1024**2:
                raise ValueError(
                    "Reserve ao menos 1 GiB de RAM disponível para a versão adicional."
                )

    def rollback(self):
        self.recover()
        if not self.state or not self.state.get("previous"):
            raise ValueError("Nenhuma versão anterior disponível para retorno.")
        old, previous = self.state["active"], self.state["previous"]
        save(
            self.state_path,
            {**self.state, "phase": "switching", "active": previous, "candidate": old},
        )
        self.restore(previous, old)
        print("Versão anterior restaurada. O banco não foi revertido.")

    def prepare(self, base):
        self.recover()
        self.preflight()
        retained = (
            [self.state["active"], self.state.get("previous")] if self.state else []
        )
        retained_images = [
            json.loads(Path(target["compose"]).read_text())["services"]["web"]["image"]
            for target in retained
            if target
        ]
        base = copy.deepcopy(base)
        for service in ("api", "web", *WORKERS):
            base["services"][service]["image"] = self.output(
                [
                    "docker",
                    "image",
                    "inspect",
                    "--format",
                    "{{.Id}}",
                    base["services"][service]["image"],
                ]
            )
        slot = (
            "green" if self.state and self.state["active"]["slot"] == "blue" else "blue"
        )
        directory = self.directory / slot
        directory.mkdir(exist_ok=True)
        if self.state and self.state.get("previous"):
            # Reusing the inactive slot consumes that older rollback target.
            self.state["previous"] = None
            save(self.state_path, self.state)
        # No credentials in the generated Nginx file; it must be readable by Nginx.
        nginx = (self.root / "frontend" / "nginx.conf").read_text()
        (directory / "web.conf").write_text(
            nginx.replace("http://api:8000", f"http://{self.project}-{slot}-api:8000")
        )
        os.chmod(directory / "web.conf", 0o644)
        metadata = json.loads(
            self.output(
                ["docker", "network", "inspect", base["networks"]["frontend"]["name"]]
            )
        )[0]
        subnets = [
            item["Subnet"]
            for item in metadata["IPAM"]["Config"]
            if ipaddress.ip_network(item["Subnet"]).version == 4
        ]
        if len(subnets) != 1:
            raise ValueError("Rede interna sem subnet IPv4 inequívoca.")
        base["x-deploy-subnet"] = subnets[0]
        candidate = {
            "slot": slot,
            "project": self.project + "-" + slot,
            "compose": str(directory / "compose.json"),
            "release": self.values["RELEASE"],
        }
        save(
            directory / "compose.json", slot_config(base, self.project, slot, directory)
        )
        if self.state:
            old = self.state["active"]
        else:
            # Preserve actual old image IDs, not tags which a build may overwrite.
            legacy = copy.deepcopy(base)
            legacy.pop("x-deploy-subnet", None)
            legacy["services"] = {
                name: legacy["services"][name] for name in ("api", "web", *WORKERS)
            }
            legacy["networks"] = {
                name: {"external": True, "name": network["name"]}
                for name, network in base["networks"].items()
            }
            legacy["volumes"] = {
                name: {"external": True, "name": base["volumes"][name]["name"]}
                for name in ("integration_keys", "mobile_releases")
            }
            for service in ("api", "web", *WORKERS):
                ids = self.run(
                    "ps", "-q", service, text=True, capture_output=True
                ).stdout.split()
                if len(ids) != 1:
                    raise ValueError(
                        f"Serviço legado {service} não identificado; não é seguro trocar o tráfego."
                    )
                container = json.loads(self.output(["docker", "inspect", ids[0]]))[0]
                legacy["services"][service]["image"] = container["Image"]
                legacy["services"][service].pop("build", None)
                legacy["services"][service].pop("depends_on", None)
            save(self.directory / "legacy.json", legacy)
            old = {
                "slot": "legacy",
                "project": self.project,
                "compose": str(self.directory / "legacy.json"),
                "release": "legacy",
            }
        # The volume holds only immutable public bundles; keep old tabs' lazy chunks.
        assets = self.project + "_web_assets"
        self.output(["docker", "volume", "create", assets])
        images = [base["services"]["web"]["image"], *retained_images]
        snapshot = json.loads(Path(old["compose"]).read_text())
        images.append(snapshot["services"]["web"]["image"])
        try:
            stage_assets(self.output, images, assets)
        except subprocess.CalledProcessError:
            raise ValueError(
                "Falha ao preparar/verificar os arquivos públicos; tráfego atual preservado."
            ) from None
        labels = {
            "traefik.enable": "true",
            "traefik.docker.network": self.values["TRAEFIK_NETWORK"],
            "traefik.http.routers.rotafy-rolling.rule": "Host(`rotafy.nexusdataanalytics.tech`)",
            "traefik.http.routers.rotafy-rolling.entrypoints": self.values[
                "TRAEFIK_HTTPS_ENTRYPOINT"
            ],
            "traefik.http.routers.rotafy-rolling.tls": "true",
            "traefik.http.routers.rotafy-rolling.tls.certresolver": self.values[
                "TRAEFIK_CERTRESOLVER"
            ],
            "traefik.http.routers.rotafy-rolling.priority": "200",
            "traefik.http.routers.rotafy-rolling.service": "rotafy-rolling",
            "traefik.http.services.rotafy-rolling.loadbalancer.server.port": "80",
        }
        save(
            self.gateway / "compose.json",
            {
                "services": {
                    "gateway": {
                        "image": "nginx:1.28-alpine",
                        "restart": "unless-stopped",
                        "labels": labels,
                        "logging": base["services"]["web"]["logging"],
                        "networks": ["frontend", "traefik"],
                        "volumes": [
                            str(self.gateway) + ":/etc/nginx/conf.d:ro",
                            assets + ":/srv/assets:ro",
                        ],
                        "healthcheck": {
                            "test": [
                                "CMD",
                                "wget",
                                "-q",
                                "-O",
                                "/dev/null",
                                "http://127.0.0.1/api/v1/health",
                            ],
                            "interval": "5s",
                            "timeout": "5s",
                            "retries": 12,
                        },
                    }
                },
                "networks": {
                    "frontend": {
                        "external": True,
                        "name": base["networks"]["frontend"]["name"],
                    },
                    "traefik": {
                        "external": True,
                        "name": self.values["TRAEFIK_NETWORK"],
                    },
                },
                "volumes": {assets: {"external": True, "name": assets}},
            },
        )
        return old, candidate

    def readiness_error(self, candidate, stage):
        details = []
        try:
            ids = self.compose(candidate, "ps", "-aq", "api", "web").stdout.split()
            containers = (
                json.loads(self.output(["docker", "inspect", *ids])) if ids else []
            )
            for container in containers:
                service = (
                    container["Config"]
                    .get("Labels", {})
                    .get("com.docker.compose.service")
                )
                if service not in ("api", "web"):
                    continue
                state = container["State"]
                health = state.get("Health", {})
                checks = health.get("Log", [])
                probe = checks[-1].get("ExitCode") if checks else None
                details.append(
                    f"{service}: estado={state.get('Status')}, saúde={health.get('Status', 'sem teste')}, saída={state.get('ExitCode')}, teste={probe}"
                )
        except (subprocess.CalledProcessError, ValueError, KeyError, OSError):
            details.append("estado dos containers indisponível")
        return ValueError(
            f"Nova versão não validada (slot {candidate['slot']}, {stage}); tráfego não alterado. "
            + ("; ".join(details) or "Nenhum container novo identificado.")
        )

    def publish(self, old, candidate):
        print("Validando web/API novas; a versão atual continua atendendo.")
        stage = "inicialização dos serviços"
        try:
            self.compose(
                candidate,
                "up",
                "-d",
                "--no-deps",
                "--wait",
                "--wait-timeout",
                "180",
                "api",
                "web",
            )
            stage = "comunicação entre API e web"
            # Ensure assets and API really belong to the candidate before public routing.
            self.compose(
                candidate,
                "exec",
                "-T",
                "api",
                "python",
                "-c",
                f"import json,urllib.request; assert json.load(urllib.request.urlopen('http://{self.project}-{candidate['slot']}-web/version.json', timeout=10))['version']=={candidate['release']!r}",
            )
        except subprocess.CalledProcessError:
            raise self.readiness_error(candidate, stage) from None
        save(
            self.state_path,
            {"phase": "switching", "active": old, "candidate": candidate},
        )
        print(
            "Nova versão pronta. Trocando tráfego e finalizando os envios anteriores."
        )
        try:
            self.route(candidate)
            self.stopped(old)
            self.start_workers(candidate)
        except Exception:
            self.restore(old, candidate)
            raise
        self.state = {
            "active": candidate,
            "previous": old,
            "phase": "ready",
            "changed_at": time.time(),
        }
        save(self.state_path, self.state)
        if old["slot"] != "legacy":
            self.run("stop", "--timeout", str(DRAIN_SECONDS), "api", "web")
        print(
            "Nova versão ativa. A anterior foi preservada para retorno; banco e arquivos compartilhados."
        )
