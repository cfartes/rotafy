import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Linux/Bash required")
class UpdateTests(unittest.TestCase):
    def run_update(
        self, project="nexus-rotafy-tech", database=True, active="nexus-rotafy-tech"
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "app"
            (checkout / ".git").mkdir(parents=True)
            (checkout / "scripts").mkdir()
            (checkout / ".env.production").write_text(
                f'DEPLOY_PROJECT="{project}"\n' if project else "RELEASE=existing\n"
            )
            (checkout / "scripts/deploy_vps.py").write_text(
                'import sys\nprint("DEPLOY", *sys.argv[1:])\n'
            )
            binaries = root / "bin"
            binaries.mkdir()
            log = root / "actions"
            commands = {
                "git": """#!/bin/bash
echo "git $*" >> "$UPDATE_LOG"
case "$*" in
  *"remote get-url origin"*) echo 'https://github.com/cfartes/rotafy.git' ;;
  *"branch --show-current"*) echo main ;;
esac
""",
                "docker": """#!/bin/bash
echo "docker $*" >> "$UPDATE_LOG"
if [[ "$1" == ps ]]; then echo "$ACTIVE_PROJECT"; fi
if [[ "$1 $2" == "volume inspect" && "$HAS_DATABASE" == 0 ]]; then exit 1; fi
""",
            }
            for name, content in commands.items():
                file = binaries / name
                file.write_text(content)
                file.chmod(0o755)
            script = Path(__file__).resolve().parents[1] / "update_vps.sh"
            result = subprocess.run(
                ["bash", str(script), "--dry-run"],
                text=True,
                capture_output=True,
                check=False,
                env={
                    **os.environ,
                    "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
                    "ROTAFY_INSTALL_DIR": str(checkout),
                    "UPDATE_LOG": str(log),
                    "HAS_DATABASE": str(int(database)),
                    "ACTIVE_PROJECT": active,
                },
            )
            return result, log.read_text() if log.exists() else ""

    def test_updates_only_identified_existing_installation_and_forwards_arguments(self):
        result, log = self.run_update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("pull --ff-only origin main", log)
        self.assertIn("volume inspect nexus-rotafy-tech_database", log)
        self.assertIn("DEPLOY --project nexus-rotafy-tech --dry-run", result.stdout)
        self.assertNotIn("nexus-rotafy-prod", log)

    def test_legacy_environment_is_rejected_before_git_or_docker_actions(self):
        result, log = self.run_update(project="nexus-rotafy-prod")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("pull --ff-only", log)
        self.assertNotIn("DEPLOY ", result.stdout)

    def test_recognizes_running_legacy_project_without_environment_marker(self):
        result, log = self.run_update(project=None, active="nexus-rotafy-prod")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("volume inspect nexus-rotafy-prod_database", log)
        self.assertNotIn("volume inspect nexus-rotafy-tech_database", log)
        self.assertIn("DEPLOY --project nexus-rotafy-prod --dry-run", result.stdout)

    def test_unknown_active_project_is_rejected(self):
        result, log = self.run_update(project=None, active="unrelated-app")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("pull --ff-only", log)

    def test_missing_database_does_not_create_an_installation(self):
        result, log = self.run_update(database=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("pull --ff-only", log)
        self.assertNotIn("DEPLOY --dry-run", result.stdout)


if __name__ == "__main__":
    unittest.main()
