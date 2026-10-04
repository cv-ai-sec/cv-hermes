# Architecture

This project runs the official [Hermes Agent](https://hermes-agent.nousresearch.com/) container image, configured
with its recommended settings, in a controlled virtual machine with Docker. It is a learning lab for the OWASP
Top 10 for LLM Applications.

## Components

| Component | Role |
|---|---|
| Agent | The official Hermes Agent container. Handles the chat interface, dashboard, and API. |
| Egress proxy | The agent's only route to the internet. Allows a short list of hostnames. |
| Language model | Served by LM Studio on the host machine. Local only. |
| Logging | The agent's log files are shipped to a log store and viewed in Grafana. |

## Network layout

- The agent and the egress proxy share an internal network. The proxy holds a fixed address, and the agent's
  addresses come from a separate range, so the two never collide.
- The proxy has a second network for its own outbound traffic.
- The logging stack sits on its own internal network, with no internet route.
- The agent's own outbound traffic is limited to the proxy and the local model server. Everything else is
  rejected by the host firewall.

Addresses and subnets are kept in local documentation, not here.

## Traffic rules

- **Agent outbound:** the proxy and the local model server only.
- **Proxy outbound:** allowed hostnames only, on the secure web port.
- **Logging stack:** no outbound route.
- **Enforcement:** host firewall rules, applied at boot by a system service. Container networks can bypass
  some firewall rules by default, so the rules are placed where the container runtime evaluates them first.

## Logging

The agent writes plain-text logs to a folder on the VM. A log shipper reads them read-only and sends them to
the log store. Grafana queries the log store. Logs can contain chat content, so they stay inside the lab.

## Trust boundaries

- **Secrets:** the agent reads its credentials from a local file inside its container. The compose file holds
  placeholders only.
- **Local models only:** the model runs on the host machine. No cloud provider is configured.
- **Dashboard and API:** both require credentials and are reachable only from the lab network.
- **The agent's terminal:** unsandboxed, so commands run inside the container without extra isolation. This is
  an accepted risk; see [SECURITY.md](SECURITY.md).

