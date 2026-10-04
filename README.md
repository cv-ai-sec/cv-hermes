# cv-hermes

A cybersecurity learning environment built on the existing **Hermes Agent** by Nous Research,
repurposed for learning the **OWASP Top 10 for LLM Applications** and for detecting rogue entities on
its own lab network. It runs in a controlled VM and Docker stack. This project does not reimplement
Hermes. It runs the official agent image, configures it with the recommended settings, and adds the
lab-specific pieces: a restricted network, a persona and scope for security learning
(`config/soul.md`), and Grafana for observing the agent's own health.

- Hermes Agent (official project): **[hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/)**
- Hermes quickstart (what the official image and gateway expect): **[quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)**

Discord and the dashboard are interfaces to the same agent. The only internet access is
`discord.com` and `gateway.discord.gg`, through an egress proxy; the LLM is local (LM Studio on
the host). See [docs/SECURITY.md](docs/SECURITY.md) for the exact network posture and accepted
risks.

**[→ Live concept preview](https://cv-ai-sec.github.io/cv-hermes/)** — a static page showing the
architecture, a mock Grafana dashboard, and a mock Discord/Revolt conversation, viewable without
running any of this yourself (no build step; see "Publishing the concept page" below).

Runs inside a VirtualBox Rocky Linux 9 VM — see [docs/INSTALL.md](docs/INSTALL.md) for the full
setup (any hypervisor in the spec table below works; that guide covers VirtualBox specifically).
Already running and just need a URL or a command? See [docs/USER-GUIDE.md](docs/USER-GUIDE.md).

## Mission

The lab focuses on the **OWASP Top 10 for LLM Applications** (2025):

| ID | Risk |
|---|---|
| LLM01 | Prompt Injection (direct and indirect) |
| LLM02 | Sensitive Information Disclosure |
| LLM03 | Supply Chain Vulnerabilities |
| LLM04 | Data and Model Poisoning |
| LLM05 | Improper Output Handling |
| LLM06 | Excessive Agency |
| LLM07 | System Prompt Leakage |
| LLM08 | Vector and Embedding Weaknesses |
| LLM09 | Misinformation / Overreliance |
| LLM10 | Unbounded Consumption |

The classic web OWASP Top 10 is out of scope for this project.

**Detection goal:** the agent should help detect rogue entities on the lab network: unauthorized
MCP servers, rogue or unknown agents, and unexpected services on the VM's network. Nothing in this
repo implements that yet. It needs network visibility the agent doesn't have today, which is a
deliberate firewall change to be decided and recorded separately before it's built.

The lab is for learning on systems you own, inside a controlled VM and Docker environment. The agent's persona and scope live in
[config/soul.md](config/soul.md), editable without touching code.

**Current state, honestly:** the agent runs on the official image, but this repo does not yet add
OWASP LLM lab targets or tooling. Hermes's built-in capabilities are what the official image
provides, and the lab's own additions will be introduced one at a time. Any tool the agent gets is
explicitly allowlisted, not given broad reach upfront. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s Trust boundaries section for why that matters here.

## Why this is safe to publish

- **Local models only.** The LLM is LM Studio on the Windows host. No cloud LLM provider is allowed
  for now (see docs/SECURITY.md).
- **Secrets never touch a file.** `hermes_agent/config.py` reads `DISCORD_TOKEN`/`LLM_API_KEY` from
  the environment only, never from the YAML config — `.env` is git-ignored, only `.env.example`
  with placeholders is committed. See [docs/SECURITY.md](docs/SECURITY.md).
- **Not air-gapped; egress is restricted.** hermes-agent reaches the internet only through an
  egress proxy that allows `discord.com` and `gateway.discord.gg`. Loki, Promtail, and Grafana
  have no internet access. The LLM is local (LM Studio on the host). See
  [docs/SECURITY.md](docs/SECURITY.md) for the layers and accepted risks.
- **Every container hardened:** `cap_drop: [ALL]`, `no-new-privileges`, read-only root filesystem,
  non-root user, SELinux `:Z` volume labels — on every service, not just the agent.
- **Sandboxed file tools.** The one tool category the LLM can call is path-contained to
  `./workspace` on every invocation, not just at startup — see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s Trust boundaries section.
- **Hermes GUI has zero backend of its own.** It's a static file server with no database, no
  secrets, and no network reach beyond serving the page — the browser talks to Hermes Core's API
  directly. Neither that API nor the GUI itself has app-level auth; both rely entirely on firewalld
  restricting their ports to `LOCAL_SUBNET` — see
  [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s Trust boundaries section before widening either
  rule.
- **Pre-commit security checklist:** see [docs/SECURITY.md](docs/SECURITY.md) — followed before
  every commit, not just the first one.

## Architecture

```
Discord -> Hermes Core -> LLM API
             ^  |      \
   /api/*,  /ws  \       -> yt-dlp -> Notes service -> ./notes/*.md
    |              \                         |
Hermes GUI          Task DB (SQLite, owned solely by Hermes Core)
 (browser)     JSON logs (incl. health heartbeat) -> Promtail -> Loki <- Grafana
```

Full diagram, component table, and trust-boundary breakdown:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Commands

| Command | What it does |
|---|---|
| `!hermes <anything>` or `@Hermes <anything>` | Plain chat — forwarded to the configured LLM, same as before |
| `!hermes summarize <youtube-url>` | Fetches the video's transcript (captions only, no audio transcription), generates a structured markdown note via the LLM, saves it to `./notes/`, and replies with a proof-of-work summary (word count, processing time) |
| `!hermes task <title>` | Creates a tracked task entry (`Backlog` status) in the local SQLite task DB, no note generation |

All three commands work identically from **Hermes GUI**'s Chat tab (`http://<VM-IP>:<HERMES_GUI_PORT>`,
default `8504`, no prefix needed — just type `summarize <url>` directly) as they do from Discord — no
Discord account, server, or token required to talk to Hermes at all. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Chat platform adapters" section.

A task can also be created/viewed/edited from Hermes GUI's **Tasks** tab — same SQLite file (via
Hermes Core's `/api/tasks`), no chat command required. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Hermes GUI" section for what it does and the one
thing it deliberately doesn't do yet (auto-processing a task added there).

Discord and Hermes GUI's web chat are both fully supported. Revolt is scaffolded but not currently
functional — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Chat platform adapters" section for
why (`revolt.py`'s dependencies conflict with `openai`'s, not a design choice).

## Hermes GUI & health

**Hermes GUI** (`http://<VM-IP>:<HERMES_GUI_PORT>`, default `8504`) is the one dashboard for
everything: Chat, Tasks, a real-time Health tab, and a labeled "coming soon" Reasoning Canvas
placeholder (it needs an actual LLM tool-calling loop first — not built yet, see
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)). It's a pure static page with zero backend of its
own — every chat message and task read/write goes straight from your browser to Hermes Core's API
(`WEB_CHAT_PORT`).

Grafana's "Hermes health" panel row tracks the same underlying signal as the GUI's Health tab, as a
historical trend instead of a live snapshot: whether [config/soul.md](config/soul.md) actually
loaded (vs. silently falling back to a generic default), whether the configured LLM backend is
reachable, estimated context-window usage per chat call, and uptime/active-adapters. Full
explanation: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)'s "Hermes health" section. Day-2
reference: [docs/USER-GUIDE.md](docs/USER-GUIDE.md)'s "Checking Hermes's health" section.

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
├── hermes_agent/      # "Hermes Core" — main.py, config.py, metrics.py, health.py, soul.py, tools.py, Dockerfile
│   ├── adapters/      # ChatAdapter interface + Discord + the core API/WS adapter (Revolt scaffolded, not yet functional)
│   ├── bot/           # commands.py — the one place command logic lives, platform-agnostic
│   └── services/      # transcript_service.py, task_db.py (sole owner of tasks.db), notes_service.py
├── hermes-gui/        # Unified dashboard (Chat/Tasks/Health/Reasoning Canvas) — static-only, own Dockerfile, no DB access
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
cp .env.example .env   # compose-level values: IPs, ports, image tags, GRAFANA_ADMIN_PASSWORD
# hermes-data/.env: DISCORD_BOT_TOKEN, OPENAI_API_KEY (LM Studio placeholder), dashboard and API keys
docker compose up -d
# or: podman-compose up -d
docker compose logs -f hermes-agent
```

Then find the VM's host-only IP (`ip -4 addr show` on the VM) and open, from a machine on
`LOCAL_SUBNET`:

- `http://<that-ip>:<HERMES_DASHBOARD_PORT>` (default `9119`): the official Hermes dashboard. Login required.
- `http://<that-ip>:<GRAFANA_PORT>` (default `3000`): Grafana. The Hermes health panels need the
  Promtail update noted in `docs/INSTALL.md` step 10 before they show data.

## Running alongside ai-cybersecurity-devops-lab

This project runs in its **own dedicated VM** (named `hermes agent` in VirtualBox), not the same VM
as [`ai-cybersecurity-devops-lab`](../ai-cybersecurity-devops-lab) — but both VMs share this
workspace's VirtualBox host-only network and can both reach the same LM Studio
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
