#!/usr/bin/env bash
#
# Provisions a fresh Rocky Linux 9 VM to run the Hermes Agent stack:
#   - base packages + git
#   - Docker CE + the Compose plugin (podman-compose also works with this
#     repo's docker-compose.yml if you prefer Podman; see README.md)
#   - firewalld: SSH kept on, Grafana (3000) opened to the local subnet only,
#     everything else closed to the outside
#   - an explicit firewalld rule blocking the observability network (Loki/
#     Promtail/Grafana) from reaching the internet at all, since none of
#     those three services need outbound access to do their job
#
# Run as a user with sudo rights: `sudo bash scripts/00_setup_rocky9_host.sh`

set -euo pipefail

# --- Configuration you should check before running ---------------------------
# The subnet allowed to reach Grafana. Default assumes a typical home/lab /24;
# change this to match your actual LAN or VM host-only network.
LOCAL_SUBNET="${LOCAL_SUBNET:-192.168.1.0/24}"

# Must match GRAFANA_PORT in .env (default 3000). Change this if 3000 is
# already taken on this VM — e.g. ai-cybersecurity-devops-lab's open-webui
# also defaults to host port 3000 — and set the same value in both places.
GRAFANA_PORT="${GRAFANA_PORT:-3000}"

# Must match the `obs-net` subnet in docker-compose.yml. Loki/Promtail/Grafana
# live here and have no legitimate reason to reach the internet — see
# README.md's "Network isolation" section for why this is split from the
# agent-net that hermes-agent itself uses (that one DOES need outbound
# internet, for Discord + the LLM API, so it is intentionally NOT blocked
# here; this script only blocks the observability subnet).
OBS_NET_SUBNET="${OBS_NET_SUBNET:-172.28.9.0/24}"
# -------------------------------------------------------------------------------

if [[ $EUID -ne 0 ]]; then
  echo "Run this script as root (sudo bash $0)" >&2
  exit 1
fi

echo "==> Updating base packages"
dnf -y update

echo "==> Installing prerequisites (git, firewalld, dnf-plugins-core)"
dnf -y install git firewalld dnf-plugins-core

systemctl enable --now firewalld

echo "==> Installing Docker CE + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo
  dnf -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker

  # Allow the invoking non-root user (via sudo) to run docker without sudo.
  if [[ -n "${SUDO_USER:-}" ]]; then
    usermod -aG docker "$SUDO_USER"
    echo "    Added $SUDO_USER to the docker group — log out/in for it to take effect."
  fi
else
  echo "    docker already installed, skipping"
fi

echo "==> Configuring SELinux (enforcing mode expected; container bind mounts use :Z labels)"
setenforce 1 2>/dev/null || true
sed -i 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config
# container_manage_cgroup is the one commonly-needed boolean for rootful
# container runtimes managing cgroups under enforcing SELinux; bind-mount
# labeling itself is handled per-volume by the :Z flags already in
# docker-compose.yml, not by a boolean.
setsebool -P container_manage_cgroup on

echo "==> Configuring firewalld"
# Keep SSH reachable (default service, already enabled on most Rocky installs,
# but make it explicit here).
firewall-cmd --permanent --add-service=ssh

# Grafana: allow only from the local subnet, not the world.
firewall-cmd --permanent --zone=public --add-rich-rule="rule family='ipv4' source address='${LOCAL_SUBNET}' port port='${GRAFANA_PORT}' protocol='tcp' accept"
# Explicitly drop any other inbound attempt at this port that didn't match the rule above.
firewall-cmd --permanent --zone=public --remove-port="${GRAFANA_PORT}/tcp" 2>/dev/null || true

# Observability stack (Loki/Promtail/Grafana) has no legitimate reason to
# reach the internet — block its egress outright at the host firewall rather
# than relying on Docker network config alone (Docker's `internal: true`
# would also break Grafana's published port, which we need; see this
# workspace's standing CLAUDE.md rule on air-gapped container labs for why
# that flag is avoided here).
firewall-cmd --permanent --direct --add-rule ipv4 filter FORWARD 0 \
  -s "${OBS_NET_SUBNET}" -j REJECT

firewall-cmd --reload

echo "==> Done."
echo "    Grafana will be reachable at http://<VM_IP>:${GRAFANA_PORT} from ${LOCAL_SUBNET} only."
echo "    The observability network (${OBS_NET_SUBNET}) cannot reach the internet."
echo "    hermes-agent's own network (agent-net) is left open for outbound Discord/LLM traffic."
echo "    Next: cp .env.example .env, fill in real values, then: docker compose up -d"
