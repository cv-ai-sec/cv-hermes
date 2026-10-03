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
| Task dashboard (view/add/edit tasks) | `http://<VM_host-only-IP>:<TASK_DASHBOARD_PORT>` (default port `8502`) | No login of its own — only reachable from `LOCAL_SUBNET` (firewalld-enforced), same posture as Grafana. Reads/writes the same `./data/tasks.db` the bot uses. |
| Local web chat (talk to Hermes without Discord) | `http://<VM_host-only-IP>:<WEB_CHAT_PORT>` (default port `8503`) | No login of its own — same firewalld posture as above. `summarize <url>`/`task <title>`/plain chat all work exactly like they do in Discord. |
| Loki (log storage) | No direct URL — query only through Grafana | Not published outside `obs-net`; use Grafana's **Explore** view for ad-hoc LogQL, or the pre-built dashboard panels. |
| SSH into the VM | `ssh -p 2223 <user>@127.0.0.1` (from Windows) | Port `2223`, not `2222` — `2222` is `ai-cybersecurity-devops-lab`'s VM. See `firewall-audit-log` if this ever changes. |
| LM Studio (LLM backend) | Running on Windows, not browsable — check its own Developer tab | Reachable from the VM at `http://host.docker.internal:1234` (mapped to `HOST_LM_STUDIO_IP`). |
| Discord bot | Interact in whatever server you invited it to | Commands below. |
| Raw log file | `docker compose exec hermes-agent cat /var/log/hermes/hermes.jsonl` | Same file Promtail tails — useful when a Grafana panel looks wrong. |
| Generated notes | `./notes/` on the VM (bind-mounted from the repo root) | One `.md` file per completed `summarize` task. View rendered in a browser: see below. |
| Task DB | `./data/tasks.db` on the VM (SQLite) | Inspect with `sqlite3 data/tasks.db "SELECT * FROM tasks;"` if `sqlite3` is installed on the VM, or copy the file off and open it locally. |
| Hermes's persona (soul.md) | `./config/soul.md` on the VM | Plain markdown — edit and `docker compose up -d --force-recreate hermes-agent` to apply. If missing, a generic built-in default is used instead (visible as `soul.md loaded = DEFAULT` on the Grafana health panel). |
| Hermes health | Grafana → "Hermes health" row on the overview dashboard | LLM reachability, soul.md load status, uptime, active adapters, estimated context-window usage. See below and `docs/ARCHITECTURE.md`'s "Hermes health" section. |

## Viewing a generated note rendered in a browser

No new container or dependency — a tiny static HTML page (`scripts/notes-viewer.html`) renders
Markdown client-side via a JS library loaded from a CDN. Reached over an SSH tunnel, so nothing new
is exposed on the firewall.

**1. Open a tunnel from Windows** (rides over the SSH port already allowed):
```powershell
ssh -p 2223 -L 8000:localhost:8000 <user>@127.0.0.1
```

**2. In that same SSH session, serve the repo root** (not `notes/` — the viewer page needs to be
served alongside `notes/`, not from inside it):
```bash
cd ~/cv-hermes
python3 -m http.server 8000
```

**3. From Windows, open:**
```
http://localhost:8000/scripts/notes-viewer.html?file=4-EpWpZpQbXrg.md
```
(swap in the actual filename — check `http://localhost:8000/notes/` for the exact name, or click
the "Browse notes/" link on the viewer page itself)

`Ctrl+C` the `http.server` process when you're done — it only runs for as long as you need it.

## Graceful startup

1. Start the VM (from Windows):
   ```powershell
   & "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" startvm "hermes agent" --type headless
   ```
2. Give it a few seconds to boot, then confirm SSH is up: `ssh -p 2223 <user>@127.0.0.1`
3. Bring up the stack:
   ```bash
   docker compose up -d
   ```
4. Verify all five containers actually started clean, not crash-looping:
   ```bash
   docker compose ps
   ```
   You should see `hermes-agent`, `loki`, `promtail`, `grafana`, and `task-dashboard`, all showing
   `Up`/`running` — not `Restarting`. If `hermes-agent` is restarting, check
   `docker compose logs hermes-agent --tail 30` before assuming the rest of the stack is fine (it's
   the one container doing the most at startup: Discord gateway connection, loading `config/soul.md`,
   and starting the embedded web chat server all happen here).
5. Confirm each surface is actually reachable, not just "container says Up" — from Windows, using the
   VM's host-only IP (see above):
   - **Grafana** (`:3000`, or your `GRAFANA_PORT`): log in, open **Hermes Agent Overview**, and check
     the **Hermes health** row — `LLM backend reachable` should read `UP` within one
     `HEALTH_INTERVAL_SECONDS` interval (default 300s) of startup. If it's still blank after that,
     the heartbeat loop hasn't run yet or `hermes-agent` is unhealthy — see "Checking Hermes's
     health" below.
   - **Local web chat** (`:8503`, or your `WEB_CHAT_PORT`): page loads, status line reads
     "connected", and a plain message gets a reply.
   - **Task dashboard** (`:8502`, or your `TASK_DASHBOARD_PORT`): page loads and shows existing
     tasks (or an empty board on a fresh install) — confirms it can read `./data/tasks.db`.
   - **Discord**: send `!hermes <anything>` in the server you invited the bot to and confirm a reply
     — confirms the Discord gateway connection actually came up, which `docker compose ps` alone
     doesn't tell you (a container can show `Up` while still failing to log in to Discord).

## Graceful shutdown

**Stop the containers first, don't just kill the VM:**
```bash
docker compose down
```
This sends `SIGTERM` and waits for each container to exit cleanly, rather than a hard kill — this
matters here specifically because `hermes-agent` **and** `task-dashboard` both hold open SQLite
connections to the same `./data/tasks.db` (WAL mode), and Grafana/Loki have their own on-disk state;
an abrupt stop risks leaving either in a corrupted or inconsistent state. `docker compose down` does
**not** delete volumes or your bind-mounted `./notes`/`./data`/`./workspace` — your data is still
there after this.

**Then shut down the VM's OS itself cleanly, over SSH — not a VirtualBox power-off:**
```bash
sudo shutdown -h now
```

**Avoid this for routine shutdowns:**
```powershell
# Only as a last resort for a genuinely hung VM — equivalent to pulling the power cord
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" controlvm "hermes agent" poweroff
```
A hard `poweroff` skips the OS's own unmount/flush sequence entirely — the same class of risk
`docker compose down` avoids one layer up, just at the filesystem level instead of the container
level.

**Confirm it's actually off** (from Windows, a few seconds after step above):
```powershell
& "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" list runningvms
```
`hermes agent` should no longer appear in the list.

## Checking Hermes's health

Open Grafana → the "Hermes health" row on the overview dashboard. Four things to glance at:

- **LLM backend reachable** — `DOWN` means LM Studio (or whatever `LLM_API_BASE` points at) isn't
  responding; check it's actually running before assuming the bot is broken.
- **soul.md loaded** — `DEFAULT (soul.md missing)` means `./config/soul.md` wasn't found or was
  empty at startup, and Hermes is running on the generic built-in persona instead. Fix the file and
  recreate the container (see the table above).
- **Context window usage (p50/p95)** — climbing toward 100% means messages are getting close to
  `LLM_CONTEXT_WINDOW`; a spike in "Context window overflow errors" right below it means they
  actually overflowed. There's no truncation on plain chat (unlike the `summarize` pipeline, which
  already truncates transcripts) — a very long message can hit this. See
  `docs/ARCHITECTURE.md`'s "Hermes health" section for why that's accepted today.
- **Active adapters** — confirms which chat platforms are actually live (`discord`, `web`), useful
  after changing `WEB_CHAT_ENABLED`/tokens in `.env`.

Heartbeat runs every `HEALTH_INTERVAL_SECONDS` (default 300s) — a stat panel going blank for longer
than that means the heartbeat loop itself stopped, which usually means `hermes-agent` crashed; check
`docker compose logs hermes-agent`.

## Bot/chat commands (Discord and local web chat — Revolt is scaffolded but not currently functional, see ARCHITECTURE.md)

| Command | What happens |
|---|---|
| `!hermes <anything>` or `@Hermes <anything>` | Plain chat with the configured LLM |
| `!hermes summarize <youtube-url>` | Fetches captions, generates a markdown note, replies with a proof-of-work summary |
| `!hermes task <title>` | Creates a tracked task entry (no note generated) |

(`!hermes ` is the default Discord prefix — check `COMMAND_PREFIX`/`chat.command_prefix` in your
config if you've changed it. The web chat has no prefix at all — just type `summarize <url>`,
`task <title>`, or plain chat directly.)

A task can also be created straight from the [task dashboard](#quick-reference) — it lands in
`Backlog` the same as `!hermes task` would. **Note:** the bot does not currently poll for
dashboard-created tasks and act on them automatically — see ARCHITECTURE.md's "task dashboard"
section for why that's a deliberate, scoped-out gap rather than a bug. Today the dashboard is a
viewing/organizing surface (and a faster way to jot a task than typing a Discord command); it is not
yet a queue Hermes drains on its own.

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
