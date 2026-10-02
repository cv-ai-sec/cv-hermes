# Hermes Agent — Discord Lab (Rocky Linux 9 VM)

A sandboxed, containerized Discord agent (Hermes) running inside a dedicated Rocky
Linux 9 VM, with local observability via Grafana + Loki + Promtail (token usage,
task latency, tool calls, error rates). Everything here is meant to be provisioned
and run **inside the VM** — nothing in this repo installs anything on the physical
host workstation.

## System specifications

| Resource     | Minimum                          | Recommended                 |
|--------------|-----------------------------------|------------------------------|
| OS           | Rocky Linux 9 (x86_64, Minimal)   | same                         |
| Hypervisor   | VMware Workstation / Proxmox / Hyper-V / VirtualBox / KVM | same |
| vCPU         | 4                                 | 8                            |
| RAM          | 8 GB                              | 16 GB+                       |
| Disk         | 50 GB SSD/NVMe (thin provisioned) | same                         |
| Network      | NAT or Bridged, SSH enabled, `firewalld` active | same |

## Architecture

```
+-----------------------------------------------------------------------------------+
|                           PHYSICAL HOST WORKSTATION                               |
|                                                                                     |
|   +---------------------------------------------------------------------------+   |
|   |                       ROCKY LINUX 9 VIRTUAL MACHINE                       |   |
|   |                                                                             |   |
|   |   firewalld: SSH allowed; 3000/tcp allowed from LOCAL_SUBNET only;        |   |
|   |   obs-net subnet FORWARD-REJECTed to the internet (see "Network           |   |
|   |   isolation" below)                                                        |   |
|   |                                                                             |   |
|   |   +---------------- agent-net (outbound internet OK) -------------------+ |   |
|   |   |                                                                     | |   |
|   |   |  [ Hermes Agent Container ]                                         | |   |
|   |   |     - Outbound: Discord Gateway (wss) + LLM API                     | |   |
|   |   |     - cap_drop: ALL, no-new-privileges, read_only root, non-root    | |   |
|   |   |     - Isolated ./workspace volume (:Z) — sandboxed file tools only  | |   |
|   |   |     - Writes structured JSON logs -> hermes-logs volume            | |   |
|   |   |                                                                     | |   |
|   |   +---------------------------------------------------------------------+ |   |
|   |                                 |                                          |   |
|   |                                 | (hermes-logs volume, not network)        |   |
|   |                                 v                                          |   |
|   |   +---------------- obs-net (NO internet access) ------------------------+ |   |
|   |   |                                                                     | |   |
|   |   |  [ Promtail ] --(HTTP push :3100)--> [ Loki ] <--(query)-- [Grafana]| |   |
|   |   |                                                       (:3000, exposed| |   |
|   |   |                                                        to LOCAL_SUBNET)|   |
|   |   +---------------------------------------------------------------------+ |   |
|   |                                                                             |   |
|   +---------------------------------------------------------------------------+   |
+-----------------------------------------------------------------------------------+
```

### Network isolation — and why this is *not* the "air-gapped lab" pattern

This workspace has a standing rule that fully air-gapped container labs block
**all** egress at the host firewall. **Hermes Agent is intentionally not fully
air-gapped** — its entire purpose is reaching the Discord Gateway and an LLM API
over the internet, so blocking its egress would break the project. That's a
deliberate, accepted exception to the air-gap default, not an oversight:

- `agent-net` (hermes-agent only): outbound internet is left open. This is the
  one container in the stack that needs it.
- `obs-net` (Loki, Promtail, Grafana): **is** treated as air-gapped, because
  none of those three services have any legitimate reason to reach the
  internet. `scripts/00_setup_rocky9_host.sh` adds a `firewalld --direct`
  `FORWARD` reject rule for the `obs-net` subnet specifically — not relying on
  Docker's `internal: true` (which breaks Grafana's published port 3000; see
  this workspace's standing CLAUDE.md note on that failure mode).
- Inbound to the VM: `firewalld` only allows SSH and 3000/tcp-from-`LOCAL_SUBNET`.
  Every other container port stays unpublished/internal.

If you later add a tool to Hermes that should never phone home at all, give it
its own container on `obs-net` (or a third, equally locked-down network)
rather than loosening `agent-net`.

## Security hardening applied

- **No secrets in files.** `.env` is git-ignored; only `.env.example` with
  placeholder values is committed. `hermes_agent/config.py` reads tokens/API
  keys from the environment only — never from the YAML config file — so a
  leaked `hermes.yaml` can't leak a credential.
- **Container hardening** on every service: `cap_drop: [ALL]`,
  `security_opt: [no-new-privileges:true]`, `read_only: true` root filesystem,
  non-root user (hermes-agent runs as a fixed non-root UID baked into its
  Dockerfile), SELinux `:Z` volume labels.
- **Sandboxed workspace.** `hermes_agent/tools.py` resolves every file path
  the LLM asks to read/write and rejects anything that would escape
  `./workspace` — the one place a prompt-injected response could try a path
  traversal.
- **Tool allowlist.** `config/hermes.example.yaml` only grants the agent a
  short, explicit list of tools; it does not get an open-ended shell or
  network tool.
- **Low-cardinality log labels.** `config/promtail-config.yaml` only labels
  on `level`/`event` — never on user/guild/message IDs — so Loki's index
  doesn't blow up as usage grows.

## Setup

### 1. Provision the Rocky Linux 9 VM

Create a VM matching the specs above in your hypervisor of choice, install
Rocky Linux 9 (Minimal), enable SSH, and copy this project onto it (e.g.
`git clone` once pushed, or `scp` the folder over).

### 2. Run the host provisioning script

```bash
cd cv-hermes
sudo bash scripts/00_setup_rocky9_host.sh
```

Before running, open the script and check/edit `LOCAL_SUBNET` (the subnet
allowed to reach Grafana) and `OBS_NET_SUBNET` (must match `obs-net` in
`docker-compose.yml`, default `172.28.9.0/24`) at the top.

This installs Docker CE + the Compose plugin, `git`, configures `firewalld`
(SSH + Grafana-from-LOCAL_SUBNET-only + the obs-net egress block), and sets
the SELinux boolean containers need under enforcing mode.

> Prefer Podman? `docker-compose.yml` works with `podman-compose up -d` too —
> swap the install step in the script for `dnf install podman podman-compose`
> and skip the `docker` group step.

### 3. Configure secrets

```bash
cp .env.example .env
```

Edit `.env` and fill in:
- `DISCORD_TOKEN` / `DISCORD_APPLICATION_ID` from your bot's
  [Discord Developer Portal](https://discord.com/developers/applications) page
- `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` for whatever OpenAI-compatible
  endpoint you're using (a local model server, or a cloud provider)
- `GRAFANA_ADMIN_PASSWORD` — change this from the placeholder before first boot

`.env` is git-ignored. Never commit it.

### 4. Launch the stack

```bash
docker compose up -d
# or: podman-compose up -d
```

Check logs:

```bash
docker compose logs -f hermes-agent
```

### 5. Access Grafana

From a machine on `LOCAL_SUBNET`, open `http://<VM_IP>:3000`, log in with
`GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD` from your `.env`. The **Hermes
Agent Overview** dashboard (`dashboards/hermes-overview.json`) is
auto-provisioned and shows:
- Errors per minute
- Task latency (p50/p95)
- Token usage (prompt + completion)
- Tool calls by tool name
- Live log stream

### 6. Debugging the log pipeline

If a panel looks empty, validate the raw log file matches the schema the
pipeline expects:

```bash
docker compose exec hermes-agent python -m scripts.parse_metrics /var/log/hermes/hermes.jsonl
```

### 7. Exporting dashboard edits

If you tweak a dashboard in the Grafana UI and want to save it back to this
repo:

```bash
GRAFANA_API_TOKEN="glsa_xxx" bash scripts/export_grafana_dashboards.sh
```

(Create the token under Grafana > Administration > Service accounts — never
use your admin password here.)

## Pre-push checklist (do this before `git init`/commit/push)

- [ ] `.env` is NOT staged (`git status` should not show it)
- [ ] `grep -rniE "api_key|apikey|secret|password|token|sk-|AIza" .` over
      staged files turns up only placeholders from `.env.example`
- [ ] No real Discord token, LLM API key, or Grafana password appears in any
      committed file, including this README
- [ ] `workspace/` and `*.log` are excluded (check `.gitignore`)

## Repository layout

```
.
├── .gitignore
├── .env.example
├── docker-compose.yml
├── README.md
├── config/
│   ├── hermes.example.yaml
│   ├── loki-config.yaml
│   ├── promtail-config.yaml
│   ├── grafana-datasource.yaml
│   └── grafana-dashboards-provisioning.yaml
├── dashboards/
│   └── hermes-overview.json
├── hermes_agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── config.py
│   ├── metrics.py
│   └── tools.py
├── scripts/
│   ├── 00_setup_rocky9_host.sh
│   ├── parse_metrics.py
│   └── export_grafana_dashboards.sh
└── workspace/                # sandboxed, isolated workspace for Hermes (git-ignored contents)
```
