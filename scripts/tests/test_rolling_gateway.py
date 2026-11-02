"""Opt-in real Nginx cutover test: ROTAFY_DOCKER_TEST=1 python -m unittest ..."""

import concurrent.futures
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

from scripts.rolling_deploy import gateway_config

SERVER = """
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json,sys,time
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.flush()
        if self.path=='/slow': time.sleep(2)
        self.wfile.write(json.dumps({'release':sys.argv[2], 'cookie':self.headers.get('Cookie'), 'forwarded':self.headers.get('X-Forwarded-For')}).encode())
ThreadingHTTPServer(('0.0.0.0',int(sys.argv[1])),Handler).serve_forever()
"""


@unittest.skipUnless(
    os.environ.get("ROTAFY_DOCKER_TEST") == "1",
    "Explicit isolated Docker test required",
)
class GatewayIntegrationTests(unittest.TestCase):
    def test_idle_legacy_worker_can_stop_while_frozen(self):
        name = "rotafy-pause-test-" + str(os.getpid())

        def docker(*args):
            return subprocess.run(
                ["docker", *args], check=True, capture_output=True, text=True
            ).stdout.strip()

        try:
            docker(
                "run",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "python:3.13-slim",
                "python",
                "-u",
                "-c",
                "import time; print('ready'); time.sleep(60); print('resumed')",
            )
            for attempt in range(50):
                if "ready" in docker("logs", name):
                    break
                time.sleep(0.1)
            docker("pause", name)
            docker("kill", name)
            self.assertEqual(
                docker("inspect", "--format", "{{.State.Running}}", name), "false"
            )
            self.assertNotIn("resumed", docker("logs", name))
        finally:
            subprocess.run(
                ["docker", "rm", "-f", name], check=False, capture_output=True
            )

    def test_real_sigterm_finishes_worker_unit_before_exit(self):
        name = "rotafy-shutdown-test-" + str(os.getpid())
        helper = Path(__file__).resolve().parents[2] / "backend/app/worker_shutdown.py"
        code = """
import asyncio,sys
sys.path.insert(0,'/tmp')
from worker_shutdown import shutdown_event,pause
async def main():
    stop=shutdown_event()
    print('ready',flush=True)
    await asyncio.sleep(1)
    print('committed',flush=True)
    await pause(stop,60)
    assert stop.is_set()
asyncio.run(main())
"""

        def docker(*args):
            return subprocess.run(
                ["docker", *args], capture_output=True, text=True, check=True
            ).stdout.strip()

        try:
            docker(
                "run",
                "-d",
                "--init",
                "--name",
                name,
                "--network",
                "none",
                "-v",
                str(helper) + ":/tmp/worker_shutdown.py:ro",
                "python:3.13-slim",
                "python",
                "-u",
                "-c",
                code,
            )
            for attempt in range(50):
                if "ready" in docker("logs", name):
                    break
                time.sleep(0.1)
            docker("stop", "--timeout", "5", name)
            self.assertIn("committed", docker("logs", name))
            self.assertEqual(
                docker("inspect", "--format", "{{.State.ExitCode}}", name), "0"
            )
        finally:
            subprocess.run(
                ["docker", "rm", "-f", name], check=False, capture_output=True
            )

    def test_reload_under_load_preserves_requests_cookies_and_old_assets_and_can_rollback(
        self,
    ):
        prefix = "rotafy-cutover-test-" + str(os.getpid())
        containers = []

        def docker(*args):
            return subprocess.run(
                ["docker", *args], check=True, capture_output=True, text=True
            ).stdout.strip()

        with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
            directory = Path(temporary)
            conf = directory / "conf"
            conf.mkdir()
            assets = directory / "assets"
            assets.mkdir()
            (assets / "old-chunk.js").write_text("old bundle")
            try:
                docker("network", "create", prefix)
                for color in ("blue", "green"):
                    for role, port in (("api", 8000), ("web", 80)):
                        name = prefix + "-" + color + "-" + role
                        docker(
                            "run",
                            "-d",
                            "--name",
                            name,
                            "--network",
                            prefix,
                            "python:3.13-slim",
                            "python",
                            "-u",
                            "-c",
                            SERVER,
                            str(port),
                            color,
                        )
                        containers.append(name)

                def config(color):
                    return gateway_config(
                        prefix + "-" + color + "-api",
                        prefix + "-" + color + "-web",
                        "127.0.0.1",
                    )

                (conf / "active.conf").write_text(config("blue"))
                gateway = prefix + "-gateway"
                docker(
                    "run",
                    "-d",
                    "--name",
                    gateway,
                    "--network",
                    prefix,
                    "-p",
                    "127.0.0.1::80",
                    "-v",
                    str(conf) + ":/etc/nginx/conf.d:ro",
                    "-v",
                    str(assets) + ":/srv/assets:ro",
                    "nginx:1.28-alpine",
                )
                containers.append(gateway)
                address = "http://" + docker("port", gateway, "80").splitlines()[0]

                def request(path="/api/v1/health"):
                    with urllib.request.urlopen(
                        urllib.request.Request(
                            address + path,
                            headers={
                                "Cookie": "session=unchanged",
                                "X-Forwarded-For": "203.0.113.123",
                            },
                        ),
                        timeout=10,
                    ) as response:
                        return json.load(response)

                for attempt in range(60):
                    try:
                        self.assertEqual(request()["release"], "blue")
                        break
                    except (OSError, AssertionError):
                        if attempt == 59:
                            raise
                        time.sleep(0.2)

                errors = []
                replies = []
                stop = threading.Event()

                def load():
                    while not stop.is_set():
                        try:
                            result = request()
                            replies.append(result["release"])
                            self.assertEqual(result["cookie"], "session=unchanged")
                            self.assertNotEqual(result["forwarded"], "203.0.113.123")
                        except (OSError, ValueError, AssertionError) as error:
                            errors.append(str(error))
                        stop.wait(0.01)

                slow_headers = threading.Event()

                def slow():
                    with urllib.request.urlopen(
                        address + "/slow", timeout=10
                    ) as response:
                        slow_headers.set()
                        return json.load(response)

                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                    pending = [pool.submit(load) for _ in range(4)]
                    slow_request = pool.submit(slow)
                    try:
                        self.assertTrue(slow_headers.wait(10))
                        (conf / "active.conf").write_text(config("green"))
                        docker("exec", gateway, "nginx", "-t")
                        docker("exec", gateway, "nginx", "-s", "reload")
                        for attempt in range(50):
                            if request()["release"] == "green":
                                break
                            time.sleep(0.1)
                        self.assertEqual(request()["release"], "green")
                        self.assertEqual(
                            slow_request.result(timeout=10)["release"], "blue"
                        )
                        with urllib.request.urlopen(
                            address + "/assets/old-chunk.js"
                        ) as response:
                            self.assertEqual(response.read(), b"old bundle")
                        (conf / "active.conf").write_text(
                            "invalid nginx configuration;"
                        )
                        with self.assertRaises(subprocess.CalledProcessError):
                            docker("exec", gateway, "nginx", "-t")
                        self.assertEqual(request()["release"], "green")
                        (conf / "active.conf").write_text(config("blue"))
                        docker("exec", gateway, "nginx", "-s", "reload")
                        time.sleep(0.5)
                        self.assertEqual(request()["release"], "blue")
                    finally:
                        stop.set()
                        for future in pending:
                            future.result(timeout=10)
                self.assertEqual(errors, [])
                self.assertIn("blue", replies)
                self.assertIn("green", replies)
                self.assertGreater(len(replies), 20)
            finally:
                if containers:
                    docker("rm", "-f", *containers)
                subprocess.run(
                    ["docker", "network", "rm", prefix],
                    capture_output=True,
                    check=False,
                )


if __name__ == "__main__":
    unittest.main()
