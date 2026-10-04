# cv-hermes

A cybersecurity learning lab built on the official **Hermes Agent** by Nous Research. It runs the
agent's official Docker image with the recommended settings, and adds the lab pieces around it: a
restricted network, a Discord interface, a local model, and Grafana for observing the agent.

- Hermes Agent (official project): **[hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/)**
- Hermes quickstart: **[quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)**

## Focus

The lab focuses on the **OWASP Top 10 for LLM Applications** (2025): prompt injection (LLM01),
sensitive information disclosure (LLM02), supply chain (LLM03), data and model poisoning (LLM04),
improper output handling (LLM05), excessive agency (LLM06), system prompt leakage (LLM07), vector and
embedding weaknesses (LLM08), misinformation and overreliance (LLM09), and unbounded consumption (LLM10).
The classic web OWASP Top 10 is out of scope.

A planned addition is rogue-entity detection on the lab network (unauthorized MCP servers, rogue agents).
It is designed but not built: a separate read-only sensor will feed findings to the agent. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## What runs

| Piece | Where | Reached at |
|---|---|---|
| Hermes agent (official image, pinned) | `hermes-agent` container | Dashboard `:9119`, API `:8642` on the VM's host-only address |
| Egress proxy (Squid) | `hermes-egress-proxy` | Internal only. Allows `discord.com` and `gateway.discord.gg`. |
| Grafana, Loki, Promtail | `hermes-grafana`, `hermes-loki`, `hermes-promtail` | Grafana `:3000`. Loki internal only. |
| LLM | LM Studio on the Windows host | `:1234`, local models only |

Network posture, accepted risks, and the firewall rules are in [docs/SECURITY.md](docs/SECURITY.md).
This is **not** an air-gapped environment: the agent has two outbound hosts (Discord), through the proxy.

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md): one-time setup on the VirtualBox VM
- [docs/USER-GUIDE.md](docs/USER-GUIDE.md): day-to-day start, stop, and checks
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the pieces connect
- [docs/SECURITY.md](docs/SECURITY.md): posture, accepted risks, pre-commit checks

## Secrets

Real values never go in this repo. The compose `.env` holds addresses and ports. The agent's secrets
(Discord token, dashboard login, API key) go in `hermes-data/.env`. Both are git-ignored, and
`.env.example` and `hermes-data/.env.example` hold placeholders only.
