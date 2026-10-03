# cv-hermes

A sandboxed agent (Hermes) meant for cybersecurity work and building awareness of its own lab
network — not a chatbot that happens to answer cybersecurity questions. Discord and a local web UI
are both just interfaces to the same agent; work gets tracked as tasks on a browser dashboard; and
Hermes's own health (LLM reachability, persona status, context-window usage) plus token usage,
latency, and errors are all visible in Grafana, without any of that data leaving the VM except
Hermes's own traffic to Discord, YouTube (for transcript fetching), and your chosen LLM API.

**[→ Live concept preview](https://cv-ai-sec.github.io/cv-hermes/)** — a static page showing the
architecture, a mock Grafana dashboard, and a mock Discord/Revolt conversation, viewable without
running any of this yourself (no build step; see "Publishing the concept page" below).

Runs inside a VirtualBox Rocky Linux 9 VM — see [docs/INSTALL.md](docs/INSTALL.md) for the full
setup (any hypervisor in the spec table below works; that guide covers VirtualBox specifically).
Already running and just need a URL or a command? See [docs/USER-GUIDE.md](docs/USER-GUIDE.md).

## Mission

Hermes's purpose is to help investigate and understand its own network and systems, and to do
cybersecurity-adjacent work — not to be a general-purpose chatbot. Its persona and scope live in
[config/soul.md](config/soul.md), editable without touching code. Everything it does is tracked as a
task rather than lost in chat scrollback, every capability it has is sandboxed and explicitly
allowlisted, and every metric about what it's actually doing — cost, latency, errors, its own
health — is visible on a local dashboard, not buried in stdout.

**Current state, honestly:** the concrete tools Hermes has today are a sandboxed workspace
(read/write/list files in `./workspace`) and the `summarize`/`task` pipeline — not yet any
network-scanning or log-analysis tooling of its own. Cybersecurity-specific tools are the direction
this project is heading, added deliberately one at a time behind the same explicit allowlist
(`tools.allowed` in `config/hermes.example.yaml`) rather than given broad reach upfront. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s Trust boundaries section for why that allowlist model
matters more here than in a typical chatbot.

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
- **No new attack surface from the local web chat or task dashboard.** Both are unauthenticated by
  design, like Grafana, and both rely entirely on firewalld restricting their ports to
  `LOCAL_SUBNET` — see their entries in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s Trust
  boundaries section before widening either rule.
- **Pre-commit security checklist:** see [docs/SECURITY.md](docs/SECURITY.md) — followed before
  every commit, not just the first one.

## Architecture

```
Discord     \
Web chat UI  -> Hermes Agent -> LLM API
                        |      \
                        |       -> yt-dlp -> Notes service -> ./notes/*.md
                        |                          |
                        |                     Task DB (SQLite) <-> Task Dashboard (browser)
                   JSON logs (incl. health heartbeat) -> Promtail -> Loki <- Grafana
```

Full diagram, component table, and trust-boundary breakdown:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Commands

| Command | What it does |
|---|---|
| `!hermes <anything>` or `@Hermes <anything>` | Plain chat — forwarded to the configured LLM, same as before |
| `!hermes summarize <youtube-url>` | Fetches the video's transcript (captions only, no audio transcription), generates a structured markdown note via the LLM, saves it to `./notes/`, and replies with a proof-of-work summary (word count, processing time) |
| `!hermes task <title>` | Creates a tracked task entry (`Backlog` status) in the local SQLite task DB, no note generation |

All three commands work identically from the **local web chat** (`http://<VM-IP>:<WEB_CHAT_PORT>`,
default `8503`, no prefix needed — just type `summarize <url>` directly) as they do from Discord — no
Discord account, server, or token required to talk to Hermes at all. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Chat platform adapters" section.

A task can also be created/viewed/edited from the browser-based **task dashboard**
(`task_dashboard/`, `TASK_DASHBOARD_PORT` in `.env`, default `8502`) — same SQLite file, no chat
command required. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Task dashboard" section for
what it does and the one thing it deliberately doesn't do yet (auto-processing a task added there).

Discord and the local web chat are both fully supported. Revolt is scaffolded but not currently
functional — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Chat platform adapters" section for
why (`revolt.py`'s dependencies conflict with `openai`'s, not a design choice).

## Hermes health

Grafana's "Hermes health" panel row tracks things that used to be invisible: whether
[config/soul.md](config/soul.md) actually loaded (vs. silently falling back to a generic default),
whether the configured LLM backend is reachable, estimated context-window usage per chat call, and
uptime/active-adapters. Full explanation: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Hermes
health" section. Day-2 reference: [docs/USER-GUIDE.md](docs/USER-GUIDE.md)'s "Checking Hermes's
health" section.

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
├── config/           # hermes.example.yaml, soul.md (Hermes's persona), loki/promtail/grafana provisioning
├── dashboards/       # hermes-overview.json — auto-provisioned Grafana dashboard, incl. Hermes health row
├── hermes_agent/      # main.py, config.py, metrics.py, health.py, soul.py, tools.py, Dockerfile
│   ├── adapters/      # ChatAdapter interface + Discord + web chat (Revolt scaffolded, not yet functional)
│   │   └── web_static/ # index.html — the local web chat page
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

Then find the VM's host-only IP (`ip addr show | grep 192.168.56`) and open, from a machine on
`LOCAL_SUBNET`:

- `http://<that-ip>:<GRAFANA_PORT>` (default `3000`) — the **Hermes Agent Overview** dashboard,
  auto-provisioned, including the "Hermes health" row.
- `http://<that-ip>:<WEB_CHAT_PORT>` (default `8503`) — chat with Hermes without Discord.
- `http://<that-ip>:<TASK_DASHBOARD_PORT>` (default `8502`) — view/add/edit tasks.

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
