# Security & Secret Hygiene

This project is designed to be safe to publish publicly on GitHub — the code and configuration,
that is, not the live bot itself (your `.env` holds a real Discord token and LLM API key, and never
leaves your machine). That safety comes from process, not luck — follow this checklist every time,
not just on the first commit.

## Design constraints

- **Local models only, for now.** The LLM is LM Studio on the Windows host, reached over the
  host-only network (`tcp/1234`). No cloud LLM provider (OpenAI, Anthropic, and similar) is
  permitted. Adding one requires a new audit-log entry, a change to the egress allowlist, and an
  update to this section.
- **Not air-gapped. Network-restricted.** The VM is not an air-gapped environment. The hermes-agent
  needs two internet hosts (`discord.com` and `gateway.discord.gg`), and the VM keeps a NAT adapter
  for installs. Restrictions apply in layers:
  - **Egress proxy.** hermes-agent's only route out is a Squid proxy (`config/egress-proxy/`),
    which tunnels only to the hostnames in `allowed-domains.txt`. It doesn't inspect TLS, so it
    checks hostnames, not paths.
  - **Host firewall.** `scripts/01_apply_hermes_egress_policy.sh` rejects every other outbound
    connection from the agent network, and allows the proxy only tcp/443 and DNS.
  - **Observability network.** `obs-net` (Loki/Promtail/Grafana) is blocked from the internet
    entirely, by `scripts/00_setup_rocky9_host.sh`.
  - **Accepted risks** (recorded in the cv-hermes audit log): HTTPS to the two allowed hosts can
    carry malicious payloads or data out; DNS resolution isn't restricted to specific resolvers;
    the proxy allows any path on the allowed hostnames. The agent also reaches LM Studio on the
    Windows host (`tcp/1234`), a local-only path.
  Docker's `internal: true` is not used, since it breaks published ports. See
  `docs/ARCHITECTURE.md`'s Trust boundaries section.
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
- **The Hermes dashboard requires login; the API uses a key.** The dashboard (`9119`) requires
  `HERMES_DASHBOARD_BASIC_AUTH_*` credentials on any non-loopback bind, and the API (`8642`)
  requires `API_SERVER_KEY`. Both bind to `HERMES_BIND_IP` (the VM's host-only address), and
  firewalld restricts them to `LOCAL_SUBNET`. Grafana has its own login.
- **`config/soul.md` is plain-text persona config, not a secret.** It's committed to the repo
  intentionally (unlike `.env`) — never put credentials, internal IPs, or anything sensitive in it,
  since it ships with the code, not with `.env`.

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
   `hermes_agent/requirements.txt` or `hermes-gui/requirements.txt` before adding it (discord.py
   and aiohttp are Apache-2.0, yt-dlp is Unlicense/public-domain, fastapi and uvicorn are MIT — keep
   new additions MIT/Apache-2.0/BSD-equivalent). `revolt.py` is deliberately NOT installed (dependency
   conflict with `openai` — see `requirements.txt`); if it's ever re-added, verify its actual license
   on whatever version installs, not assumed.
7. **soul.md stays generic.** If `config/soul.md` was edited this session, confirm nothing specific
   to your real network (hostnames, real IP ranges, internal service names) was written into it —
   it's committed to the repo, unlike `.env`.

## If you find something real

Stop. Do not commit, do not push, and do not just delete the line and continue silently — flag it
so the exposure (if already committed locally) can be handled properly. A secret that was only ever
staged/committed locally and never pushed is easy to fix (amend or drop the commit). A secret that
reached a remote needs to be treated as compromised: rotate it (regenerate the Discord bot token /
LLM API key), then clean history.
