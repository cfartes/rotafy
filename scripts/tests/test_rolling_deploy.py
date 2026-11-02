import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.production import command
from scripts.rolling_deploy import RollingDeployment, gateway_config, save, slot_config


class RollingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.deployment = RollingDeployment(
            self.root, "nexus-rotafy-tech", Mock(), Mock(), {"RELEASE": "new"}
        )
        self.old = {
            "slot": "blue",
            "release": "old",
            "project": "test-blue",
            "compose": "old.json",
        }
        self.new = {
            "slot": "green",
            "release": "new",
            "project": "test-green",
            "compose": "new.json",
        }
        self.deployment.compose = Mock(return_value=SimpleNamespace(stdout=""))
        self.deployment.route = Mock()
        self.deployment.stopped = Mock()
        self.deployment.start_workers = Mock()

    def test_cutover_precedes_exclusive_worker_handoff_and_preserves_previous(self):
        calls = Mock()
        for name in ("route", "stopped", "start_workers"):
            calls.attach_mock(getattr(self.deployment, name), name)
        self.deployment.publish(self.old, self.new)
        self.assertEqual(
            [call[0] for call in calls.mock_calls],
            ["route", "stopped", "start_workers"],
        )
        self.deployment.stopped.assert_called_once_with(self.old)
        state = json.loads(self.deployment.state_path.read_text())
        self.assertEqual(state["active"], self.new)
        self.assertEqual(state["previous"], self.old)

    def test_failed_candidate_never_switches_or_stops_active_workers(self):
        self.deployment.compose.side_effect = subprocess_error = RuntimeError(
            "unhealthy"
        )
        with self.assertRaisesRegex(RuntimeError, "unhealthy"):
            self.deployment.publish(self.old, self.new)
        self.assertIsNotNone(subprocess_error)
        self.deployment.route.assert_not_called()
        self.deployment.stopped.assert_not_called()
        self.assertFalse(self.deployment.state_path.exists())

    def test_failed_workers_stop_new_before_restoring_old(self):
        events = []
        self.deployment.route.side_effect = lambda target: events.append(
            ("route", target["slot"])
        )
        self.deployment.stopped.side_effect = lambda target: events.append(
            ("stop", target["slot"])
        )

        def start(target, reuse=False):
            events.append(("start", target["slot"]))
            if target == self.new:
                raise RuntimeError("worker failed")

        self.deployment.start_workers.side_effect = start
        with self.assertRaisesRegex(RuntimeError, "worker failed"):
            self.deployment.publish(self.old, self.new)
        self.assertEqual(
            events[-3:], [("stop", "green"), ("route", "blue"), ("start", "blue")]
        )
        self.assertEqual(
            json.loads(self.deployment.state_path.read_text())["active"], self.old
        )

    def test_interrupted_cutover_recovers_before_another_deploy(self):
        self.deployment.state = {
            "phase": "switching",
            "active": self.old,
            "candidate": self.new,
        }
        with self.assertRaisesRegex(ValueError, "recuperada"):
            self.deployment.recover()
        self.deployment.stopped.assert_called_once_with(self.new)
        self.deployment.start_workers.assert_called_once_with(self.old, reuse=True)

    def test_rollback_never_runs_migration_or_deletes_data(self):
        self.deployment.state = {
            "phase": "ready",
            "active": self.new,
            "previous": self.old,
        }
        self.deployment.rollback()
        self.deployment.stopped.assert_called_once_with(self.new)
        self.deployment.route.assert_called_once_with(self.old)
        self.deployment.compose.assert_not_called()

    def test_drain_window_prevents_reusing_previous_api(self):
        self.deployment.state = {
            "phase": "ready",
            "active": self.old,
            "changed_at": time.time(),
        }
        with self.assertRaisesRegex(ValueError, "5 minutos"):
            self.deployment.preflight()

    def test_forced_worker_kill_blocks_new_senders(self):
        self.deployment.compose.return_value.stdout = "worker-id"
        self.deployment.output.return_value = json.dumps(
            [{"State": {"Running": False, "ExitCode": 137}}]
        )
        with self.assertRaisesRegex(ValueError, "prazo"):
            RollingDeployment.stopped(self.deployment, self.old)

    def test_legacy_workers_resume_if_busy_and_stop_only_after_drain(self):
        target = {
            **self.old,
            "slot": "legacy",
            "compose": str(self.root / "legacy.json"),
        }
        save(Path(target["compose"]), {"networks": {"database": {"name": "dbnet"}}})
        metadata = [
            {
                "Id": "worker",
                "NetworkSettings": {"Networks": {"dbnet": {"IPAddress": "172.20.0.3"}}},
                "State": {"Paused": True},
            }
        ]
        self.deployment.output.side_effect = lambda args: (
            json.dumps(metadata) if args[1] == "inspect" else ""
        )
        self.deployment.run.side_effect = [
            SimpleNamespace(stdout="1"),
            SimpleNamespace(stdout="0"),
        ]
        self.deployment.compose.return_value.stdout = "worker"
        with patch("scripts.rolling_deploy.time.sleep"):
            self.deployment.stop_legacy(target, ["worker"])
        commands = [call.args[0][1] for call in self.deployment.output.call_args_list]
        self.assertEqual(commands.count("pause"), 2)
        self.assertEqual(commands.count("unpause"), 1)
        self.assertEqual(commands.count("kill"), 1)
        self.assertGreater(commands.index("kill"), commands.index("unpause"))
        self.assertIn("pg_stat_activity", self.deployment.run.call_args.args[-1])

    def test_failed_legacy_drain_check_always_unpauses_workers(self):
        target = {
            **self.old,
            "slot": "legacy",
            "compose": str(self.root / "legacy.json"),
        }
        save(Path(target["compose"]), {"networks": {"database": {"name": "dbnet"}}})
        metadata = [
            {
                "Id": "worker",
                "NetworkSettings": {"Networks": {"dbnet": {"IPAddress": "172.20.0.3"}}},
                "State": {"Paused": True},
            }
        ]
        self.deployment.output.side_effect = lambda args: (
            json.dumps(metadata) if args[1] == "inspect" else ""
        )
        self.deployment.compose.return_value.stdout = "worker"
        self.deployment.run.side_effect = ValueError("database check failed")
        with self.assertRaisesRegex(ValueError, "database check"):
            self.deployment.stop_legacy(target, ["worker"])
        commands = [call.args[0][1] for call in self.deployment.output.call_args_list]
        self.assertIn("unpause", commands)
        self.assertNotIn("kill", commands)

    def test_operator_commands_follow_active_slot_but_db_stays_on_base(self):
        save(self.deployment.state_path, {"phase": "ready", "active": self.new})
        (self.root / ".env.production").write_text("DEPLOY_PROJECT=nexus-rotafy-tech\n")
        selected = command(self.root, ["logs", "api"])
        self.assertIn("test-green", selected)
        self.assertNotIn(".env.production", selected)
        self.assertIn("nexus-rotafy-tech", command(self.root, ["--base", "exec", "db"]))

    def test_slot_configuration_cannot_recreate_db_or_expose_direct_routers(self):
        service = {
            "image": "image:new",
            "command": ["uvicorn", "--forwarded-allow-ips", "old-proxy"],
            "build": {},
            "depends_on": {"db": {}},
            "labels": {"traefik.enable": "true"},
            "volumes": [
                {
                    "type": "volume",
                    "source": "integration_keys",
                    "target": "/run/rotafy",
                    "read_only": True,
                }
            ],
        }
        base = {
            "services": {
                name: copy.deepcopy(service)
                for name in ("api", "web", "billing", "email", "geocoding", "whatsapp")
            },
            "volumes": {"integration_keys": {"name": "existing_keys"}},
            "networks": {
                "database": {"name": "existing_db_net"},
                "frontend": {"name": "existing_frontend"},
            },
            "x-deploy-subnet": "172.20.0.0/24",
        }
        config = slot_config(base, "project", "blue", self.root)
        self.assertNotIn("db", config["services"])
        self.assertEqual(
            config["volumes"]["integration_keys"],
            {"external": True, "name": "existing_keys"},
        )
        self.assertEqual(config["services"]["api"]["command"][-1], "172.20.0.0/24")
        for item in config["services"].values():
            self.assertNotIn("depends_on", item)
            self.assertEqual(item["labels"], {"traefik.enable": "false"})
        self.assertEqual(base["services"]["api"]["command"][-1], "old-proxy")

    def test_first_preparation_pins_images_and_preserves_a_safe_legacy_snapshot(self):
        (self.root / "frontend").mkdir()
        (self.root / "frontend/nginx.conf").write_text("proxy_pass http://api:8000;")
        service = {
            "image": "image:new",
            "command": ["uvicorn", "--forwarded-allow-ips", "old"],
            "build": {},
            "depends_on": {"db": {}},
            "logging": {"driver": "json-file"},
            "volumes": [],
        }
        base = {
            "services": {
                name: copy.deepcopy(service)
                for name in (
                    "api",
                    "web",
                    "billing",
                    "email",
                    "geocoding",
                    "whatsapp",
                    "db",
                    "bootstrap",
                )
            },
            "networks": {
                name: {"name": "existing_" + name}
                for name in ("database", "frontend", "email_egress")
            },
            "volumes": {
                name: {"name": "existing_" + name}
                for name in ("database", "integration_keys", "mobile_releases")
            },
        }

        def output(args):
            if args[1:3] == ["image", "inspect"]:
                return "sha256:" + "a" * 64
            if args[1:3] == ["network", "inspect"]:
                return '[{"IPAM":{"Config":[{"Subnet":"172.20.0.0/24"}]}}]'
            if args[1] == "inspect":
                return json.dumps([{"Image": "sha256:" + "b" * 64}])
            return ""

        self.deployment.output.side_effect = output
        self.deployment.run.return_value = SimpleNamespace(stdout="old-container")
        self.deployment.values.update(
            TRAEFIK_NETWORK="proxy",
            TRAEFIK_HTTPS_ENTRYPOINT="websecure",
            TRAEFIK_CERTRESOLVER="le",
        )
        with patch.object(self.deployment, "preflight"):
            old, candidate = self.deployment.prepare(base)
        saved = json.loads(Path(candidate["compose"]).read_text())
        legacy = json.loads(Path(old["compose"]).read_text())
        self.assertEqual(saved["services"]["api"]["image"], "sha256:" + "a" * 64)
        self.assertEqual(legacy["services"]["api"]["image"], "sha256:" + "b" * 64)
        self.assertNotIn("db", legacy["services"])
        self.assertNotIn("bootstrap", legacy["services"])
        self.assertNotIn("database", legacy["volumes"])
        self.assertTrue(
            all(volume["external"] for volume in legacy["volumes"].values())
        )
        self.assertNotIn("depends_on", legacy["services"]["api"])
        self.deployment.compose.assert_not_called()

    def test_gateway_trusts_only_proxy_and_keeps_sensitive_paths_out_of_access_logs(
        self,
    ):
        config = gateway_config("blue-api", "blue-web", "172.20.0.2")
        self.assertIn("set_real_ip_from 172.20.0.2;", config)
        self.assertIn("proxy_set_header X-Forwarded-For $remote_addr;", config)
        self.assertIn("access_log off;", config)
        self.assertIn("error_log /dev/stderr crit;", config)
        self.assertIn("location ^~ /assets/", config)
        with self.assertRaises(ValueError):
            gateway_config("api", "web", "0.0.0.0/0")


if __name__ == "__main__":
    unittest.main()
