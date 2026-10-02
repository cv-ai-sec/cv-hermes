# Architecture

```mermaid
graph LR
  A[Discord Gateway] <-->|wss, via NAT adapter| B[Hermes Agent]
  B -->|chat completion| C[LM Studio on Windows host]
  B -->|JSON log lines, shared volume| D[Promtail]
  D -->|HTTP push :3100| E[Loki]
  F[Grafana] -->|query| E
  U[User's browser] -->|host-only IP, LOCAL_SUBNET only| F
```

`C` defaults to LM Studio running on the Windows host, reached over VirtualBox's host-only adapter
(`host.docker.internal` → `HOST_LM_STUDIO_IP`, same pattern as `ai-cybersecurity-devops-lab`) — swap
`LLM_API_BASE`/`LLM_API_KEY` in `.env` for a cloud provider instead if you'd rather not run a local
model.

## Components

| Component | Role | Network exposure |
|---|---|---|
| Hermes Agent (`hermes_agent/`) | discord.py bot + OpenAI-compatible LLM client; sandboxed file tools | `agent-net` — the one container allowed outbound internet, to the Discord Gateway (NAT adapter) and LM Studio on the Windows host (host-only adapter) |
| Loki (`config/loki-config.yaml`) | Log storage | `obs-net` only — no internet, see Trust boundaries |
| Promtail (`config/promtail-config.yaml`) | Tails the shared `hermes-logs` volume, ships lines to Loki | `obs-net` only — no internet |
| Grafana (`dashboards/hermes-overview.json`) | Dashboards over Loki: errors/min, task latency p50/p95, token usage, tool calls, live log stream | `obs-net` + one published port (`GRAFANA_PORT`), reached via the VM's host-only IP and firewalld-restricted to `LOCAL_SUBNET` — no NAT port-forward (see `docs/INSTALL.md` for why) |
| Sandboxed workspace (`hermes_agent/tools.py`, `./workspace`) | File read/write tools the LLM can call | No network role — a filesystem boundary, not a network one |

## Trust boundaries

- **Discord message → LLM:** every inbound message is treated as untrusted input to the model, not
  as instructions to the agent process itself. The agent never executes shell commands or arbitrary
  code derived from a message — the only actions available to the LLM are the three tools in
  `config/hermes.example.yaml`'s `tools.allowed` list.
- **LLM response → filesystem:** `hermes_agent/tools.py`'s `WorkspaceTools._resolve()` is the one
  place a prompt-injected or hallucinated file path (e.g. `../../etc/passwd`) gets checked and
  rejected, on every call, not just at startup. This is the sandbox boundary for the one tool
  category the agent has.
- **Secrets → config:** `hermes_agent/config.py` reads `DISCORD_TOKEN` and `LLM_API_KEY` from the
  environment only, never from `hermes.yaml`. A leaked or accidentally-committed YAML config file
  cannot leak a credential, because the credential was never representable there.
- **agent-net vs. obs-net:** this is a deliberate, documented exception to this workspace's default
  "air-gapped container lab" posture (see `docs/SECURITY.md`). Hermes's entire purpose requires
  reaching the Discord Gateway and an LLM API, so `agent-net` is left open. `obs-net`
  (Loki/Promtail/Grafana) has no such requirement and stays firewalld-blocked from the internet —
  the exception is scoped to exactly the one container that needs it, not the whole stack.
