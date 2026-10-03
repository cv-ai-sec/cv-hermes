# cv-hermes

A sandboxed, containerized Discord agent (Hermes Agent: discord.py + an OpenAI-compatible LLM
client) running inside a dedicated Rocky Linux 9 VM, with local observability via Grafana + Loki +
Promtail — token usage, task latency, tool calls, and error rates, all tracked without any data
leaving the VM except Hermes's own traffic to Discord and your chosen LLM API.

**[→ Live concept preview](https://cv-ai-sec.github.io/cv-hermes/)** — a static page showing the
architecture, a mock Grafana dashboard, and a mock Discord/Revolt conversation, viewable without
running any of this yourself (no build step; see "Publishing the concept page" below).

Runs inside a VirtualBox Rocky Linux 9 VM — see [docs/INSTALL.md](docs/INSTALL.md) for the full
setup (any hypervisor in the spec table below works; that guide covers VirtualBox specifically).
Already running and just need a URL or a command? See [docs/USER-GUIDE.md](docs/USER-GUIDE.md).

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
  the internet (Discord, the configured LLM API, and YouTube for transcript fetching);
  Loki/Promtail/Grafana/task-dashboard are firewalld-blocked from all outbound traffic, since none
  of them need it. Full reasoning in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **Every container hardened:** `cap_drop: [ALL]`, `no-new-privileges`, read-only root filesystem,
  non-root user, SELinux `:Z` volume labels — on every service, not just the agent.
- **Sandboxed file tools.** The one tool category the LLM can call is path-contained to
  `./workspace` on every invocation, not just at startup — see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s Trust boundaries section.
- **Pre-commit security checklist:** see [docs/SECURITY.md](docs/SECURITY.md) — followed before
  every commit, not just the first one.

## Architecture

```
Discord <-> Hermes Agent -> LLM API
                        |      \
                        |       -> yt-dlp -> Notes service -> ./notes/*.md
                        |                          |
                        |                     Task DB (SQLite) <-> Task Dashboard (browser)
                   JSON logs -> Promtail -> Loki <- Grafana
```

Full diagram, component table, and trust-boundary breakdown:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Commands

| Command | What it does |
|---|---|
| `!hermes <anything>` or `@Hermes <anything>` | Plain chat — forwarded to the configured LLM, same as before |
| `!hermes summarize <youtube-url>` | Fetches the video's transcript (captions only, no audio transcription), generates a structured markdown note via the LLM, saves it to `./notes/`, and replies with a proof-of-work summary (word count, processing time) |
| `!hermes task <title>` | Creates a tracked task entry (`Backlog` status) in the local SQLite task DB, no note generation |

A task can also be created/viewed/edited from the browser-based **task dashboard**
(`task_dashboard/`, `TASK_DASHBOARD_PORT` in `.env`, default `8502`) — same SQLite file, no Discord
command required. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Task dashboard" section for
what it does and the one thing it deliberately doesn't do yet (auto-processing a task added there).

Discord is fully supported. Revolt is scaffolded but not currently functional — see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Chat platform adapters" section for why
(`revolt.py`'s dependencies conflict with `openai`'s, not a design choice).

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
├── .nojekyll         # forces GitHub Pages to serve index.html directly, no Jekyll build
├── index.html        # static concept/demo page for GitHub Pages — no build step, no live data
├── docker-compose.yml
├── README.md
├── docs/             # ARCHITECTURE.md, INSTALL.md, SECURITY.md, USER-GUIDE.md
├── config/           # hermes.example.yaml, loki/promtail/grafana provisioning
├── dashboards/       # hermes-overview.json — auto-provisioned Grafana dashboard
├── hermes_agent/      # main.py, config.py, metrics.py, tools.py, Dockerfile
│   ├── adapters/      # ChatAdapter interface + Discord (Revolt scaffolded, not yet functional)
│   ├── bot/           # commands.py — the one place command logic lives, platform-agnostic
│   └── services/      # transcript_service.py, task_db.py, notes_service.py
├── task_dashboard/    # FastAPI task board (view/add/edit/delete), own Dockerfile, reads ./data/tasks.db
├── scripts/          # 00_setup_rocky9_host.sh, parse_metrics.py, export_grafana_dashboards.sh, notes-viewer.html
├── workspace/        # sandboxed, isolated workspace for Hermes's chat file tools (git-ignored contents)
├── notes/            # generated markdown notes from the `summarize` command (git-ignored contents)
└── data/             # local SQLite task DB (git-ignored contents)
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

Then find the VM's host-only IP (`ip addr show | grep 192.168.56`) and open
`http://<that-ip>:<GRAFANA_PORT>` (default `3000`) from a machine on `LOCAL_SUBNET` — the **Hermes
Agent Overview** dashboard is auto-provisioned.

## Running alongside ai-cybersecurity-devops-lab

This project runs in its **own dedicated VM** (named `hermes agent` in VirtualBox), not the same VM
as [`ai-cybersecurity-devops-lab`](../ai-cybersecurity-devops-lab) — but both VMs share this
workspace's VirtualBox host-only network (`192.168.56.0/24`) and can both reach the same LM Studio
instance on the Windows host. Settings that had to be kept distinct between the two VMs:

| Setting | cv-hermes (`hermes agent` VM) | ai-cybersecurity-devops-lab (`ai_cybersecurity` VM) |
|---|---|---|
| NAT SSH forward | `127.0.0.1:2223` → guest `22` | `127.0.0.1:2222` → guest `22` |
| Dashboard access | Grafana via host-only IP, `GRAFANA_PORT` (default `3000`) — no NAT forward | open-webui via NAT forward `127.0.0.1:3000` |
| Docker network subnet | `obs-net` = `172.28.9.0/24` | `lab_internal` = `172.28.1.0/24` |

Since Grafana is reached via the VM's own host-only IP rather than a NAT-forwarded Windows port,
there's no port collision with the other lab's dashboard even with both VMs running at once — see
[docs/INSTALL.md](docs/INSTALL.md) for why NAT-forwarding Grafana is avoided in the first place
(a confirmed VirtualBox NAT bug, same one documented in the other lab's install guide).

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

## Publishing the concept page (GitHub Pages)

`index.html` at the repo root is entirely static — mock data only, not connected to any live VM,
Grafana instance, or bot. No build step, so like `llm-security-labs` (and unlike
`ai-cybersecurity-devops-lab`'s Vite dashboard), GitHub Actions isn't needed.

**One-time setup:** on GitHub, go to **Settings → Pages** and set **Source** to **Deploy from a
branch**, branch `main`, folder `/ (root)`. `.nojekyll` is already committed at the repo root — this
repo previously hit a 404 on a sibling project from GitHub Pages' default Jekyll processing
silently never completing a build; that file forces Pages to serve `index.html` directly instead.
After that one-time setup, just push to `main` and the page updates within a minute or two.

## Disclaimer

Educational/personal lab project. Run your own Discord bot at your own risk with respect to
Discord's Terms of Service and API rate limits; no production systems or third-party credentials
other than your own bot token and LLM API key are involved anywhere in this repository.
