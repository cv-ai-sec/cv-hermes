# Security & Secret Hygiene

This project is designed to be safe to publish publicly on GitHub — the code and configuration,
that is, not the live bot itself (your `.env` holds a real Discord token and LLM API key, and never
leaves your machine). That safety comes from process, not luck — follow this checklist every time,
not just on the first commit.

## Design constraints

- **Partially air-gapped, by explicit exception.** Unlike a fully air-gapped lab, Hermes Agent's
  entire purpose requires reaching the internet (the Discord Gateway, and an LLM API). Rather than
  blocking everything, the Docker network is split in two: `agent-net` (hermes-agent only, egress
  left open) and `obs-net` (Loki/Promtail/Grafana, which have no legitimate reason to reach the
  internet). `obs-net`'s egress is blocked at the host firewall (`firewalld`, see
  `docs/INSTALL.md`), not via Docker's own `internal: true` flag — that flag also silently disables
  the iptables chain `docker-proxy` needs to publish Grafana's port, so it's incompatible with this
  project's requirement to expose Grafana to `LOCAL_SUBNET`. See `docs/ARCHITECTURE.md`'s Trust
  boundaries section for the full reasoning.
- **Secrets never flow through config files.** `hermes_agent/config.py` reads `DISCORD_TOKEN` and
  `LLM_API_KEY` from the environment only — the YAML config path (`hermes.example.yaml`/
  `hermes.yaml`) is never consulted for either. A leaked or accidentally-committed config file
  cannot leak a credential.
- **Sandboxed file tools.** `hermes_agent/tools.py` resolves and verifies every path the LLM asks to
  read/write against `./workspace` before touching disk, rejecting anything that would escape it —
  the one place a prompt-injected response could attempt a path traversal.
- **Task DB is deliberately not a real external integration.** `hermes_agent/services/task_db.py` is
  a local SQLite table, not an AppFlowy/Affine connection — no API credentials, no network calls, no
  dependency on either app actually running. See `docs/ARCHITECTURE.md`'s Trust boundaries section
  for the `summarize` command's URL-fetching and LLM-output-to-disk risk reasoning too.
- **Every container hardened.** `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`,
  `read_only: true` root filesystem, non-root user, SELinux `:Z` volume labels — on every service in
  `docker-compose.yml`, not just hermes-agent.

## Pre-commit checklist (run this before every `git add`, not just the first one)

1. **Diff review, not just `git add -A`.** Run `git status` and `git diff --cached` and actually
   read what's staged before committing. Don't blind-stage a whole directory.
2. **Grep staged files for secret patterns:**
   ```
   git diff --cached | grep -iE "(api[_-]?key|apikey|secret|password|token|sk-[a-zA-Z0-9]|AIza|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)"
   ```
   Any hit needs manual review — is it a real value, or an intentional placeholder like
   `.env.example`'s `your_token_here`?
3. **No real `.env`.** Confirm `.env` never appears in `git status` as a tracked or staged file —
   `.gitignore` excludes it, but a forced `git add -f .env` would bypass that. Only `.env.example`
   with dummy values should ever be committed.
4. **No hardcoded local paths, usernames, or server IPs.** Scan for your actual Windows username,
   absolute local paths (`C:\Users\<name>\...`, `D:\Ai projects\...`), real VM/LAN IP addresses, or
   hostnames leaking into config files, comments, or log fixtures. Use relative paths and env vars
   instead.
5. **No real log or runtime artifacts.** `workspace/`, `notes/`, `data/`, `hermes-logs`/
   `loki-data`/`grafana-data` volumes, and `*.log`/`*.jsonl` files are git-ignored — verify none were
   force-added, and that any example log line or generated note checked into a doc is synthetic, not
   pulled from a real run.
6. **New dependencies are permissively licensed.** Check the license of anything added to
   `hermes_agent/requirements.txt` before adding it (discord.py and aiohttp are Apache-2.0, yt-dlp is
   Unlicense/public-domain — keep new additions MIT/Apache-2.0/BSD-equivalent; verify `revolt.py`'s
   actual license on whatever version installs, since this project added it without confirming
   against a live source).

## If you find something real

Stop. Do not commit, do not push, and do not just delete the line and continue silently — flag it
so the exposure (if already committed locally) can be handled properly. A secret that was only ever
staged/committed locally and never pushed is easy to fix (amend or drop the commit). A secret that
reached a remote needs to be treated as compromised: rotate it (regenerate the Discord bot token /
LLM API key), then clean history.
