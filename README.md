# cv-hermes

A sandboxed, containerized Discord agent (Hermes Agent: discord.py + an OpenAI-compatible LLM
client) running inside a dedicated Rocky Linux 9 VM, with local observability via Grafana + Loki +
Promtail — token usage, task latency, tool calls, and error rates, all tracked without any data
leaving the VM except Hermes's own traffic to Discord and your chosen LLM API.

Runs inside a VirtualBox Rocky Linux 9 VM — see [docs/INSTALL.md](docs/INSTALL.md) for the full
setup (any hypervisor in the spec table below works; that guide covers VirtualBox specifically).

## Mission

Run a real Discord-facing LLM agent with the blast radius of its one risky capability (file tool
access) sandboxed to a single directory, and its network reach scoped to exactly what the project
needs — while keeping every metric about what the agent is actually doing (cost, latency, errors)
visible on a local dashboard, not buried in stdout.

## Why this is safe to publish

- **Secrets never touch a file.** `hermes_agent/config.py` reads `DISCORD_TOKEN`/`LLM_API_KEY` from
  the environment only, never from the YAML config — `.env` is git-ignored, only `.env.example`
  with placeholders is committed. See [docs/SECURITY.md](docs/SECURITY.md).
- **Partially air-gapped, by documented exception.** Only the `hermes-agent` container can reach
  the internet (Discord + the configured LLM API); Loki/Promtail/Grafana are firewalld-blocked from
  all outbound traffic, since none of them need it. Full reasoning in
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **Every container hardened:** `cap_drop: [ALL]`, `no-new-privileges`, read-only root filesystem,
  non-root user, SELinux `:Z` volume labels — on every service, not just the agent.
- **Sandboxed file tools.** The one tool category the LLM can call is path-contained to
  `./workspace` on every invocation, not just at startup — see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s Trust boundaries section.
- **Pre-commit security checklist:** see [docs/SECURITY.md](docs/SECURITY.md) — followed before
  every commit, not just the first one.

## Architecture

```
Discord Gateway <-> Hermes Agent -> LLM API
                        |
                   JSON logs -> Promtail -> Loki <- Grafana
```

Full diagram, component table, and trust-boundary breakdown:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## System specifications

| Resource   | Minimum                          | Recommended    |
|------------|-----------------------------------|-----------------|
| OS         | Rocky Linux 9 (x86_64, Minimal)   | same            |
| Hypervisor | VMware Workstation / Proxmox / Hyper-V / VirtualBox / KVM | same |
| vCPU       | 4                                 | 8               |
| RAM        | 8 GB                              | 16 GB+          |
| Disk       | 50 GB SSD/NVMe (thin provisioned) | same            |
| Network    | NAT or Bridged, SSH enabled, `firewalld` active | same |

## Repository structure

```
.
├── .gitignore
├── .env.example
├── docker-compose.yml
├── README.md
├── docs/             # ARCHITECTURE.md, INSTALL.md, SECURITY.md
├── config/           # hermes.example.yaml, loki/promtail/grafana provisioning
├── dashboards/       # hermes-overview.json — auto-provisioned Grafana dashboard
├── hermes_agent/     # the bot itself: main.py, config.py, metrics.py, tools.py, Dockerfile
├── scripts/          # 00_setup_rocky9_host.sh, parse_metrics.py, export_grafana_dashboards.sh
└── workspace/        # sandboxed, isolated workspace for Hermes (git-ignored contents)
```

## Getting started

Full step-by-step setup (VirtualBox VM creation, host provisioning, firewalld, bringing up the
stack): [docs/INSTALL.md](docs/INSTALL.md).

Quick version, once the VM is provisioned (`sudo bash scripts/00_setup_rocky9_host.sh` has been
run):

```bash
cp .env.example .env   # fill in DISCORD_TOKEN, LLM_API_BASE/KEY/MODEL, GRAFANA_ADMIN_PASSWORD
docker compose up -d
# or: podman-compose up -d
docker compose logs -f hermes-agent
```

Then open `http://<VM_IP>:<GRAFANA_PORT>` (default `3000`) from a machine on `LOCAL_SUBNET` — the
**Hermes Agent Overview** dashboard is auto-provisioned.

## Running alongside other labs on the same VM

If this stack shares a VM with another project (e.g.
[`ai-cybersecurity-devops-lab`](../ai-cybersecurity-devops-lab)), check for port/subnet overlap
before bringing both up at once:

| Setting | cv-hermes | ai-cybersecurity-devops-lab |
|---|---|---|
| Dashboard host port | Grafana on `3000` (override: `GRAFANA_PORT`) | open-webui on `3000` (override: `OPEN_WEBUI_PORT`) |
| Loki host port | not published (internal-only) | `3100` (override: `LOKI_PORT`) |
| Docker network subnet | `obs-net` = `172.28.9.0/24` | `lab_internal` = `172.28.1.0/24` |

Subnets don't overlap. The **Grafana port does conflict** with the other lab's open-webui default —
set `GRAFANA_PORT` in `.env` to something else (e.g. `3001`) if running both at once, and update the
matching variable in `scripts/00_setup_rocky9_host.sh` before running it.

## Debugging the log pipeline

If a Grafana panel looks empty, validate the raw log file matches the schema the pipeline expects:

```bash
docker compose exec hermes-agent python -m scripts.parse_metrics /var/log/hermes/hermes.jsonl
```

## Exporting dashboard edits

If you tweak a dashboard in the Grafana UI and want to save it back to this repo:

```bash
GRAFANA_API_TOKEN="glsa_xxx" bash scripts/export_grafana_dashboards.sh
```

(Create the token under Grafana → Administration → Service accounts — never use your admin
password here.)

## Disclaimer

Educational/personal lab project. Run your own Discord bot at your own risk with respect to
Discord's Terms of Service and API rate limits; no production systems or third-party credentials
other than your own bot token and LLM API key are involved anywhere in this repository.
