import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Linux/Bash required")
class CleanInstallTests(unittest.TestCase):
    def run_install(self, volume="nexus-rotafy-tech_database"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "app"
            target.mkdir()
            (target / ".env.production").write_text("OLD_SECRET=not-reused\n")
            log = root / "actions"
            binaries = root / "bin"
            binaries.mkdir()
            fake_git = """#!/bin/bash
echo "git $*" >> "$TEST_LOG"
target="${@: -1}"
mkdir -p "$target/scripts"
printf 'import sys\nprint("FRESH", *sys.argv[1:])\n' > "$target/scripts/deploy_vps.py"
"""
            fake_docker = """#!/bin/bash
echo "docker $*" >> "$TEST_LOG"
if [[ "$1" == ps ]]; then echo new-container; fi
if [[ "$1 $2" == "volume ls" ]]; then echo "$TEST_VOLUME"; fi
"""
            for name, content in {"git": fake_git, "docker": fake_docker}.items():
                file = binaries / name
                file.write_text(content)
                file.chmod(0o755)
            source = (
                Path(__file__).resolve().parents[1] / "install_clean_vps.sh"
            ).read_text()
            source = source.replace(
                "install_dir=/opt/rotafy-tech", f"install_dir={target}"
            )
            source = source.replace("/opt/rotafy-install.", f"{root}/staging.")
            script = root / "install.sh"
            script.write_text(source)
            result = subprocess.run(
                ["bash", str(script)],
                check=False,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                    "TEST_LOG": str(log),
                    "TEST_VOLUME": volume,
                },
            )
            return result, log.read_text(), (target / ".env.production").exists()

    def test_fresh_sources_do_not_reuse_credentials_and_reset_only_new_project(self):
        result, log, reused = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(reused)
        self.assertIn("docker rm -f new-container", log)
        self.assertIn("docker volume rm nexus-rotafy-tech_database", log)
        self.assertNotIn("nexus-rotafy-prod", log)
        self.assertIn("FRESH --replace-legacy", result.stdout)
        self.assertLess(log.index("git clone"), log.index("docker rm"))

    def test_unexpected_volume_blocks_reset(self):
        result, log, reused = self.run_install(volume="another-app_database")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(reused)
        self.assertNotIn("docker rm", log)
        self.assertNotIn("docker volume rm", log)


if __name__ == "__main__":
    unittest.main()
