#!/usr/bin/env bash
#
# Restricts what the hermes-agent network can reach from the VM, using firewalld direct rules
# in the FORWARD chain (container traffic to the outside is forwarded through the host).
#
#   agent-net (hermes-agent) may reach ONLY:
#     - the egress proxy on tcp/3128
#     - LM Studio on the Windows host, tcp/1234
#   Everything else from agent-net is rejected.
#
#   egress-net (egress proxy) may reach ONLY:
#     - tcp/443 (the proxy then allows just the hostnames in config/egress-proxy/allowed-domains.txt)
#     - DNS (udp/tcp 53) to resolve those hostnames
#   Everything else from egress-net is rejected.
#
# Accepted risks, recorded in docs/SECURITY.md and the cv-hermes audit log: tcp/443 from the proxy
# is not limited to particular destination IPs (the hostname filter is in squid, not here), and
# DNS is not restricted to specific resolvers. Run this after `docker compose up -d` has created
# the networks, then `sudo systemctl restart docker` (firewalld reloads can drop Docker's chains).
#
# Run as root: sudo bash scripts/01_apply_hermes_egress_policy.sh
# Required environment (export, or source your local .env first):
#   LM_STUDIO_IP  -- Windows host's host-only address (HOST_LM_STUDIO_IP in .env)
#   EGRESS_PROXY_IP -- the proxy's address in agent-net (EGRESS_PROXY_IP in .env)

set -euo pipefail

: "${LM_STUDIO_IP:?set LM_STUDIO_IP (HOST_LM_STUDIO_IP from .env)}"
: "${EGRESS_PROXY_IP:?set EGRESS_PROXY_IP from .env}"
AGENT_NET_SUBNET="172.28.10.0/24"
EGRESS_NET_SUBNET="172.28.11.0/24"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (sudo bash $0)" >&2
  exit 1
fi

direct() { firewall-cmd --permanent --direct --add-rule ipv4 filter FORWARD "$@"; }

# Replies to connections that were already allowed. Without this, the rejects below would block
# the proxy's and LM Studio's responses.
direct 0 -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

direct 1 -s "$AGENT_NET_SUBNET" -d "$EGRESS_PROXY_IP" -p tcp --dport 3128 -j ACCEPT
direct 1 -s "$AGENT_NET_SUBNET" -d "$LM_STUDIO_IP" -p tcp --dport 1234 -j ACCEPT
direct 2 -s "$AGENT_NET_SUBNET" -j REJECT

direct 3 -s "$EGRESS_NET_SUBNET" -p tcp --dport 443 -j ACCEPT
direct 3 -s "$EGRESS_NET_SUBNET" -p udp --dport 53 -j ACCEPT
direct 3 -s "$EGRESS_NET_SUBNET" -p tcp --dport 53 -j ACCEPT
direct 4 -s "$EGRESS_NET_SUBNET" -j REJECT

firewall-cmd --reload
echo "==> Egress policy applied. Restart Docker so its chains are rebuilt: sudo systemctl restart docker"
