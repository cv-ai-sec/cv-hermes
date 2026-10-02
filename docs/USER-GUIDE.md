# User Guide

Day-to-day reference for a stack that's already up and running. This is different from
[INSTALL.md](INSTALL.md) (one-time setup) and [README.md](../README.md) (project overview) — this
is the page to open when you just want to know "what's the URL for X again?" or "how do I check
Y?" without re-reading the full setup guide.

## Finding the VM's IP (you'll need this for everything below)

Run **on the VM**, not Windows:

```bash
ip addr show | grep 192.168.56
```

The address shown (e.g. `192.168.56.102`) is DHCP-assigned and usually stable across reboots, but
not guaranteed — re-check here if anything below stops resolving.

## Quick reference

| What | Where | Notes |
|---|---|---|
| Grafana (dashboards) | `http://<VM_host-only-IP>:<GRAFANA_PORT>` (default port `3000`) | Login: `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` from `.env`. Only reachable from `LOCAL_SUBNET` (firewalld-enforced). |
| Loki (log storage) | No direct URL — query only through Grafana | Not published outside `obs-net`; use Grafana's **Explore** view for ad-hoc LogQL, or the pre-built dashboard panels. |
| SSH into the VM | `ssh -p 2223 <user>@127.0.0.1` (from Windows) | Port `2223`, not `2222` — `2222` is `ai-cybersecurity-devops-lab`'s VM. See `firewall-audit-log` if this ever changes. |
| LM Studio (LLM backend) | Running on Windows, not browsable — check its own Developer tab | Reachable from the VM at `http://host.docker.internal:1234` (mapped to `HOST_LM_STUDIO_IP`). |
| Discord bot | Interact in whatever server you invited it to | Commands below. |
| Raw log file | `docker compose exec hermes-agent cat /var/log/hermes/hermes.jsonl` | Same file Promtail tails — useful when a Grafana panel looks wrong. |
| Generated notes | `./notes/` on the VM (bind-mounted from the repo root) | One `.md` file per completed `summarize` task. |
| Task DB | `./data/tasks.db` on the VM (SQLite) | Inspect with `sqlite3 data/tasks.db "SELECT * FROM tasks;"` if `sqlite3` is installed on the VM, or copy the file off and open it locally. |

## Bot commands (Discord and/or Revolt, same syntax either way)

| Command | What happens |
|---|---|
| `!hermes <anything>` or `@Hermes <anything>` | Plain chat with the configured LLM |
| `!hermes summarize <youtube-url>` | Fetches captions, generates a markdown note, replies with a proof-of-work summary |
| `!hermes task <title>` | Creates a tracked task entry (no note generated) |

(`!hermes ` is the default prefix — check `COMMAND_PREFIX`/`chat.command_prefix` in your config if
you've changed it.)

## Common day-2 operations

**Check everything's running:**
```bash
docker compose ps
```

**Tail logs for one service:**
```bash
docker compose logs -f hermes-agent
docker compose logs -f grafana
```

**Restart just the bot (e.g. after editing `.env`):**
```bash
docker compose up -d --force-recreate hermes-agent
```

**Full rebuild (e.g. after a dependency change in `requirements.txt`):**
```bash
docker compose build --no-cache hermes-agent
docker compose up -d
```

**Check what's currently open/configured on the firewall side:** see this workspace's local-only
`Projects\firewall-audit-log\CURRENT-STATE.md` — not part of this repo, lives one level up in the
workspace.

**Validate the log pipeline if a Grafana panel looks empty:**
```bash
docker compose exec hermes-agent python -m scripts.parse_metrics /var/log/hermes/hermes.jsonl
```

For anything not covered here — first-time setup, firewall rules, network architecture — see
[INSTALL.md](INSTALL.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [SECURITY.md](SECURITY.md).
