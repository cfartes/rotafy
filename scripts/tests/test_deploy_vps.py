import argparse
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import deploy_vps as deploy


class DeploymentTests(unittest.TestCase):
    def test_env_round_trip_preserves_secrets_and_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / ".env.production"
            values = {
                "BOOTSTRAP_PASSWORD": "abc123456789",
                "EMAIL_FROM": "Nexus <mail@example.com>",
            }
            deploy.write_env(target, values)
            self.assertEqual(deploy.read_env(target), values)
            deploy.write_env(target, {**values, "RELEASE": "git-new"})
            self.assertEqual(
                deploy.read_env(target)["BOOTSTRAP_PASSWORD"],
                values["BOOTSTRAP_PASSWORD"],
            )

    def test_interpolation_rejected_before_replacing_existing_env(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / ".env.production"
            target.write_text("RELEASE=old\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                deploy.write_env(target, {"PASSWORD": "$UNEXPECTED"})
            self.assertEqual(target.read_text(), "RELEASE=old\n")

    def test_noninteractive_ambiguity_requires_explicit_value(self):
        with self.assertRaises(ValueError):
            deploy.choose("rede", ["one", "two"], None, True)
        self.assertEqual(deploy.choose("rede", ["one", "two"], "two", True), "two")

    def test_routing_uses_real_proxy_ip_and_explicit_configuration(self):
        args = argparse.Namespace(
            network="proxy",
            entrypoint="https",
            resolver="le",
            traefik_container="traefik",
            non_interactive=True,
        )
        proxy = {
            "Name": "/traefik",
            "Config": {
                "Image": "traefik:v3",
                "Cmd": ["--providers.docker=true"],
                "Labels": {},
            },
            "NetworkSettings": {"Networks": {"proxy": {"IPAddress": "172.19.0.2"}}},
        }

        def output(command):
            if command == ["docker", "ps", "-q"]:
                return "id"
            if command == ["docker", "inspect", "id"]:
                return json.dumps([proxy])
            return json.dumps([{"Driver": "bridge", "Internal": False}])

        with patch.object(deploy, "output", side_effect=output):
            result = deploy.routing(args, {})
            self.assertEqual(result["TRAEFIK_TRUSTED_IPS"], "172.19.0.2")
            args.network = "wrong"
            with self.assertRaises(ValueError):
                deploy.routing(args, {})

    def test_existing_database_without_credentials_blocks_before_configuration(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(deploy, "ROOT", Path(directory)),
            patch.object(deploy.sys, "platform", "linux"),
            patch.object(deploy, "output", return_value=""),
            patch.object(
                deploy.subprocess, "run", return_value=SimpleNamespace(returncode=0)
            ),
            patch.object(deploy, "routing") as routing,
        ):
            with self.assertRaisesRegex(ValueError, "Banco existente"):
                deploy.deploy(argparse.Namespace())
            routing.assert_not_called()
            self.assertFalse((Path(directory) / ".env.production").exists())

    def test_dry_run_does_not_write_env_or_start_services(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env.production.example").write_text(
                "BOOTSTRAP_EMAIL=nexus@example.com\n", encoding="utf-8"
            )
            args = argparse.Namespace(admin_email=None, dry_run=True)
            with (
                patch.object(deploy, "ROOT", root),
                patch.object(deploy.sys, "platform", "linux"),
                patch.object(
                    deploy,
                    "output",
                    side_effect=lambda command: (
                        "abc123" if "rev-parse" in command else ""
                    ),
                ),
                patch.object(
                    deploy.subprocess, "run", return_value=SimpleNamespace(returncode=1)
                ),
                patch.object(deploy, "routing", return_value={}),
                patch.object(deploy, "write_env") as write,
            ):
                deploy.deploy(args)
                write.assert_not_called()
                self.assertFalse((root / ".env.production").exists())

    def test_failed_backup_prevents_application_start_and_migrations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            values = {
                key: "a" * 64
                for key in (
                    "POSTGRES_PASSWORD",
                    "APP_DB_PASSWORD",
                    "PLATFORM_DB_PASSWORD",
                    "BOOTSTRAP_PASSWORD",
                )
            }
            values["BOOTSTRAP_EMAIL"] = "nexus@example.com"
            deploy.write_env(root / ".env.production", values)
            (root / ".env.production.example").write_text("", encoding="utf-8")
            args = argparse.Namespace(admin_email=None, dry_run=False)
            with (
                patch.object(deploy, "ROOT", root),
                patch.object(deploy.sys, "platform", "linux"),
                patch.object(
                    deploy,
                    "output",
                    side_effect=lambda command: (
                        "abc123" if "rev-parse" in command else ""
                    ),
                ),
                patch.object(deploy, "routing", return_value={}),
                patch.object(
                    deploy, "execute", return_value=SimpleNamespace(returncode=0)
                ) as execute,
                patch.object(
                    deploy.subprocess,
                    "run",
                    side_effect=[
                        SimpleNamespace(returncode=0),
                        SimpleNamespace(returncode=1),
                    ],
                ),
            ):
                with self.assertRaisesRegex(ValueError, "Backup falhou"):
                    deploy.deploy(args)
                started = [
                    call.args[0]
                    for call in execute.call_args_list
                    if "up" in call.args[0]
                ]
                self.assertEqual(len(started), 1)
                self.assertEqual(started[0][-1], "db")
                self.assertEqual(
                    deploy.read_env(root / ".env.production")["BOOTSTRAP_PASSWORD"],
                    values["BOOTSTRAP_PASSWORD"],
                )


if __name__ == "__main__":
    unittest.main()
