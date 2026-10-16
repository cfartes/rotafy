#!/usr/bin/env bash
# Read-only VPS diagnostics. Never prints environment variables or application logs.
set -Eeuo pipefail
printf '\n=== UTC / host ===\n'
date -u
uname -sr
if [[ -r /etc/os-release ]]; then
    grep -E '^(NAME|VERSION_ID)=' /etc/os-release || true
fi
printf '\n=== Listening TCP ports ===\n'
if command -v ss >/dev/null 2>&1; then ss -lnt; fi
printf '\n=== Firewall ===\n'
if command -v ufw >/dev/null 2>&1; then ufw status; fi
printf '\n=== SSH effective authentication policy ===\n'
if command -v sshd >/dev/null 2>&1; then
    sshd -T 2>/dev/null | grep -E '^(permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|maxauthtries|allowtcpforwarding|x11forwarding) ' || true
fi
printf '\n=== Containers of installation in current directory ===\n'
if command -v docker >/dev/null 2>&1; then
    docker version --format 'Docker server: {{.Server.Version}}'
    mapfile -t containers < <(docker ps -q --filter "label=com.docker.compose.project.working_dir=$PWD")
    if [[ ${#containers[@]} -eq 0 ]]; then
        printf 'No running Compose containers identified for this directory. Run from the installation directory.\n'
    else
        for container in "${containers[@]}"; do
            docker inspect --format 'Name={{.Name}} Image={{.Config.Image}} User={{.Config.User}} Privileged={{.HostConfig.Privileged}} ReadOnlyRootfs={{.HostConfig.ReadonlyRootfs}} Network={{.HostConfig.NetworkMode}} Ports={{json .HostConfig.PortBindings}} CapAdd={{json .HostConfig.CapAdd}} SecurityOpt={{json .HostConfig.SecurityOpt}} DockerSocket={{range .Mounts}}{{if eq .Source "/var/run/docker.sock"}}MOUNTED{{end}}{{end}}' "$container"
        done
    fi
fi
printf '\n=== Public HTTPS headers (GET, no credentials) ===\n'
if command -v curl >/dev/null 2>&1; then
    for path in / /sw.js /api/v1/health; do
        printf '\nPath: %s\n' "$path"
        curl --proto '=https' --max-time 15 -fsS -D - -o /dev/null "https://rotafy.nexusdataanalytics.tech$path" |
            grep -Ei '^(HTTP/|strict-transport-security:|content-security-policy:|x-frame-options:|x-content-type-options:|referrer-policy:|cache-control:)' || true
    done
fi
printf '\nRead-only collection finished. Inspect output before sharing host/network information. No secrets or application logs were collected.\n'
