# Architecture

This project runs the official [Hermes Agent](https://hermes-agent.nousresearch.com/) image, configured with
the recommended settings, for learning the OWASP Top 10 for LLM Applications in a controlled VM and Docker lab.
Setup concepts are in the [quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart).

## Components

```
Browser / Discord  --->  VM host-only address (192.168.56.x)
                           :9119 dashboard   :8642 API   :3000 Grafana
                              |
   Windows host                |
   LM Studio :1234 <---+  hermes-agent  ---HTTPS_PROXY--->  egress-proxy  ---443--->  discord.com
   (local models)      |      (agent-net)                    (agent-net +             gateway.discord.gg
                       +------ direct tcp/1234              egress-net)

   Promtail --> Loki --> Grafana          (obs-net, no internet)
```

| Container | Image | Role |
|---|---|---|
| `hermes-agent` | `nousresearch/hermes-agent` (pinned) | The agent: Discord gateway, dashboard, API, tools |
| `egress-proxy` | `ubuntu/squid` (pinned) | Only route out for the agent. Allows two Discord hostnames. |
| `loki`, `promtail`, `grafana` | Grafana stack (pinned) | Log storage, shipping, and dashboards. No internet. |

## Networks

| Network | Subnet | Purpose |
|---|---|---|
| `agent-net` | `172.28.10.0/24` (dynamic addresses in `.128/25`) | Agent and proxy. The proxy is reserved at `172.28.10.2`. |
| `egress-net` | `172.28.11.0/24` | The proxy's outbound side |
| `obs-net` | `172.28.9.0/24` | Loki, Promtail, Grafana |

The proxy address is reserved because a reboot once let the agent take it. Restricting dynamic addresses to the
upper half of the subnet prevents a repeat.

## Traffic rules

- **Agent outbound:** allowed only to the proxy (`:3128`) and LM Studio (`:1234`). Everything else is rejected.
- **Proxy outbound:** allowed on 443 and DNS, and the proxy itself only tunnels to the two allowlisted hostnames.
- **Observability:** no outbound route at all.
- **Enforcement:** `DOCKER-USER` iptables chain, applied at boot by `hermes-egress.service`
  (`scripts/02_apply_docker_user_rules.sh`). The firewalld direct rules in `scripts/01_*` are a record only.
  Docker evaluates `DOCKER-USER` before its own forwarding accepts, which is why it is used.

## Logging

The official image writes plain-text logs under `hermes-data/logs/`. Promtail reads them read-only as the
agent's UID and ships them to Loki. Grafana queries Loki with `{job="hermes-agent"}`.

## Trust boundaries

- **Secrets:** the agent reads its secrets from `hermes-data/.env` inside the container. The compose `.env`
  holds only addresses and ports.
- **Local models only:** LM Studio on the Windows host is the only LLM. No cloud provider is configured.
- **Dashboard and API:** both require login or a key, and are reachable only from the lab subnet.
- **The agent's terminal:** `terminal.backend: local`, so commands run inside the agent container without a
  sandbox. This is an accepted risk, see [SECURITY.md](SECURITY.md).

## Planned: rogue-entity detection (not built)

Hermes never scans the network itself. A separate read-only sensor will run discovery on an allowlisted lab
subnet and write schema-validated findings to a volume the agent reads.

- The sensor has its own firewall scope and no route to the LLM or the internet.
- Findings are structured JSON. Hostnames and banners are untrusted data (indirect prompt injection, LLM01).
- On-demand scans go through a controller that checks an allowlist, not directly from the agent.
- Trade-off: no real-time probing. The agent works from the latest completed scan.
- Adding the sensor requires a firewall change, logged in the firewall audit log before it's applied.
