#!/usr/bin/env python3
"""Docker Compose commands against the active application slot (use --base for DB)."""

import json
import os
import sys
from pathlib import Path

if __package__:
    from .deploy_vps import read_env
else:
    from deploy_vps import read_env


def command(root, args):
    state_path = root / "artifacts/deploy/state.json"
    base = args[:1] == ["--base"]
    if base:
        args = args[1:]
    if state_path.exists() and not base:
        state = json.loads(state_path.read_text())
        if state["phase"] != "ready":
            raise ValueError(
                "Atualização em recuperação; execute update_vps.sh antes de administrar o slot."
            )
        target = state["active"]
        return [
            "docker",
            "compose",
            "-p",
            target["project"],
            "-f",
            target["compose"],
            *args,
        ]
    project = read_env(root / ".env.production")["DEPLOY_PROJECT"]
    return [
        "docker",
        "compose",
        "-p",
        project,
        "--env-file",
        str(root / ".env.production"),
        "-f",
        str(root / "compose.production.yaml"),
        *args,
    ]


if __name__ == "__main__":
    try:
        os.execvp(
            "docker", command(Path(__file__).resolve().parent.parent, sys.argv[1:])
        )
    except (ValueError, KeyError) as error:
        sys.exit(str(error))
