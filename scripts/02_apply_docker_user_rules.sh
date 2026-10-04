#!/usr/bin/env bash
#
# Applies the hermes-agent egress rules to Docker's DOCKER-USER chain. Docker evaluates that chain
# before its own FORWARD accepts, so these rules are what actually stop direct internet access.
# firewalld cannot manage DOCKER-USER here (its reload fails when the chain is referenced), so this
# runs as a boot-time systemd unit instead (see docs/INSTALL.md step 9).
#
# The chain is owned entirely by this script, so it is flushed and rebuilt on every run.
# Required environment (from /etc/hermes-egress.env, root-only, never committed):
#   LM_STUDIO_IP    -- Windows host's host-only address
#   EGRESS_PROXY_IP -- the proxy's address in agent-net (172.28.10.2)

set -euo pipefail

: "${LM_STUDIO_IP:?set LM_STUDIO_IP in /etc/hermes-egress.env}"
: "${EGRESS_PROXY_IP:?set EGRESS_PROXY_IP in /etc/hermes-egress.env}"
AGENT_NET_SUBNET="172.28.10.0/24"
EGRESS_NET_SUBNET="172.28.11.0/24"
OBS_NET_SUBNET="172.28.9.0/24"

ipt() { /usr/sbin/iptables -w "$@"; }

ipt -N DOCKER-USER 2>/dev/null || true
ipt -F DOCKER-USER

ipt -A DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
ipt -A DOCKER-USER -s "$AGENT_NET_SUBNET" -d "$EGRESS_PROXY_IP" -p tcp --dport 3128 -j ACCEPT
ipt -A DOCKER-USER -s "$AGENT_NET_SUBNET" -d "$LM_STUDIO_IP" -p tcp --dport 1234 -j ACCEPT
ipt -A DOCKER-USER -s "$AGENT_NET_SUBNET" -j REJECT
ipt -A DOCKER-USER -s "$EGRESS_NET_SUBNET" -p tcp --dport 443 -j ACCEPT
ipt -A DOCKER-USER -s "$EGRESS_NET_SUBNET" -p udp --dport 53 -j ACCEPT
ipt -A DOCKER-USER -s "$EGRESS_NET_SUBNET" -p tcp --dport 53 -j ACCEPT
ipt -A DOCKER-USER -s "$EGRESS_NET_SUBNET" -j REJECT
ipt -A DOCKER-USER -s "$OBS_NET_SUBNET" -j REJECT

echo "==> DOCKER-USER egress rules applied"
