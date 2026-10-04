# Security

This repository holds code and configuration only. Live credentials, addresses, and machine details are kept
outside it, in git-ignored local files. Read this before changing anything that touches the network, secrets,
or what the agent can do.

## Design rules

- **The agent is not air-gapped.** It can reach a small allowlist of hosts through a proxy, and nothing else.
  Everything outside the allowlist is blocked at the host firewall, not just by configuration.
- **Local models only.** The language model runs on a local machine. Cloud model providers are not permitted.
  Setup must not sign in to a hosted account. Adding a provider requires a documented change to these rules.
- **Credentials are never stored in code.** Tokens, passwords, and keys live in local environment files
  that are never committed.
- **Every service that exposes a port requires authentication.** Access is limited to the lab network, not
  the wider internet.
- **Observability has no outbound route.** Logging and dashboards cannot reach the internet.

## Accepted risks

Each risk below is a known tradeoff. The operator has reviewed it and accepts it for this lab.

1. **Allowed hosts can carry malicious content.** The proxy restricts destinations by hostname. It does not
   inspect the content or the paths of allowed traffic, so an allowed service could carry data out or deliver a
   payload.
2. **The agent can run commands inside its own container without a sandbox.** Prompt injection through the chat
   interface or the API could reach this. Mitigations: the chat bot accepts messages only from an allowlist of
   accounts, and the API requires a key.
3. **Name resolution is not restricted.** The agent can look up names, but cannot connect to them unless they
   are allowed. Lookups themselves could be used to pass small amounts of data.
4. **The language model is reached directly on the local network**, outside the proxy. This is local-only,
   but it is a path from the agent to the host.
5. **The log shipper runs with the agent's file ownership** to read logs, which may contain chat content.
   It has no internet route.
6. **The single administrator account can read the agent's data directory.** This is acceptable for a
   single-user machine and should be revisited if the machine is shared.

## Reporting

Report security problems privately to the repository owner, not in a public issue.

## Pre-commit checklist

1. Review the staged diff, and read every line before committing.
2. Scan staged content for secret-like values. Any match must be a placeholder.
3. Confirm no environment file with real values is staged. Only the `.example` files are committed.
4. Confirm no private addresses, machine names, usernames, or local paths are staged. Use placeholders.
5. Confirm no runtime data, logs, or databases are staged.
6. Keep audit records out of the repository. They are never committed.

## If a secret is exposed

Stop. Don't commit or push. A secret that exists only in an unpushed commit can be dropped. A secret that
reached a remote must be treated as compromised: rotate it first, then remove it from history.
