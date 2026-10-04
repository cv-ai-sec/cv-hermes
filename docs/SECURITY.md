# Security & Secret Hygiene

This repo is safe to publish: it contains code and configuration, never the live bot, its tokens, or
the VM's addresses. Those live only in local, git-ignored `.env` files. Follow the checklist below before
every commit.

## Design constraints

- **Not air-gapped; egress is restricted.** The agent has exactly two internet hosts, `discord.com` and
  `gateway.discord.gg`, reached only through an egress proxy. Layers:
  - **Egress proxy** (Squid): tunnels only to the allowlisted hostnames on 443. No TLS interception, so it
    checks hostnames, not paths.
  - **Host firewall:** `DOCKER-USER` rules, applied at boot, reject all other outbound traffic from the agent
    network. The proxy's own outbound is limited to 443 and DNS.
  - **Observability:** Loki, Promtail, and Grafana have no internet route.
- **Local models only, for now.** The LLM is LM Studio on the Windows host, on `tcp/1234`. No cloud LLM
  provider is permitted. Adding one requires a new audit-log entry and a change here.
  The agent wizard must be run in **Full setup** mode, not Quick Setup (which signs in to the Nous Portal).
  After setup, check `hermes-data/config.yaml` for cloud-provider entries.
- **Dashboard and API require credentials.** The dashboard (`9119`) requires basic auth; the API (`8642`)
  requires `API_SERVER_KEY`. Both bind to the VM's host-only address, and the firewall restricts them to the
  lab subnet. Grafana has its own login.
- **Secrets stay out of files that ship.** The Discord token, dashboard password, and API key live only in
  `hermes-data/.env`. The compose `.env` holds addresses and ports only.

## Accepted risks

Each of these is a known tradeoff, recorded here and in the cv-hermes audit log.

1. **Discord over 443 can carry malicious payloads or data out.** The proxy checks hostnames only, so
   content and paths on those two hosts are not inspected.
2. **The agent's terminal runs locally, without a sandbox.** The agent is configured with
   `terminal.backend: local`, so its commands run inside its container with no extra isolation. The API
   listens on `0.0.0.0` inside the container, and the host firewall limits who can reach it to the lab subnet.
   Prompt injection through Discord or the API could reach this. Mitigations: `DISCORD_ALLOWED_USERS` limits who
   can talk to the bot, and the API key limits who can call the API.
3. **DNS is not restricted to specific resolvers.** The agent's container can resolve names through Docker's
   resolver; the firewall blocks connections, not lookups. DNS tunneling is not blocked.
4. **LM Studio is reached directly.** The agent's model traffic bypasses the proxy and goes straight to the
   Windows host on `tcp/1234`. This is local-only, but it is a path from the agent to the host.
5. **Promtail runs as the agent's UID** to read the agent's logs, which may contain chat content. It has no
   internet route.
6. **Single-user VM.** The admin account has read access to `hermes-data/`, including `.env`, via an ACL.

## Pre-commit checklist

1. **Review the diff.** Run `git status` and `git diff --cached`, and read what's staged. Don't blind-stage a
   directory.
2. **Scan staged files for secret patterns:**
   ```
   git diff --cached | grep -iE "(api[_-]?key|apikey|secret|password|token|sk-[a-zA-Z0-9]|AIza|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY)"
   ```
   Any hit needs review: real value, or an intentional placeholder like `your_token_here`?
3. **No real `.env` files.** `.env` and `hermes-data/` must never appear in `git status`. Only the
   `.example` files are committed.
4. **No private addresses or local paths.** Scan for private IP ranges, `C:\Users\`, `D:\`, and usernames.
   Use placeholders such as `<VM host-only IP>` in docs.
5. **No runtime artifacts.** `hermes-data/`, named volumes, and `*.log` files are git-ignored.
6. **Keep audit details out of the repo.** Audit logs live under `Projects\` outside this repo and are never committed.

## If you find something real

Stop. Don't commit, push, or delete-and-continue silently. A secret that's only committed locally is easy to
fix (drop the commit). A secret that reached a remote must be treated as compromised: rotate it first
(regenerate the Discord token, change the dashboard password, regenerate the API key), then clean history.
