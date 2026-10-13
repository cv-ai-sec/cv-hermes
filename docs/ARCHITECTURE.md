# Architecture

This project runs the official [Hermes Agent](https://hermes-agent.nousresearch.com/) container image with its
recommended settings. It sits inside a controlled environment and is a learning lab for the OWASP Top 10 for LLM
Applications.

The network layout, host configuration, and enforcement details are private, and the rules for them are in
[SECURITY.md](SECURITY.md#buildout-and-configuration).

## Components

| Component | Role |
|---|---|
| Agent | The official agent container. Provides the chat interface, dashboard, and API. |
| Egress proxy | The agent's only route out. Allows a short list of destinations. |
| Language model | Served by a local model server on the host. No cloud provider. |
| Logging | The agent's logs are shipped to a log store and viewed in dashboards. |

## Data flow, at a high level

- Chat messages and API requests reach the agent from allowlisted users and clients.
- The agent calls the local model server for reasoning.
- Outbound requests from the agent pass through the proxy, which checks destinations.
- The agent's logs are shipped to the log store. The log store has no route outside the environment.

## Trust boundaries

- **Secrets:** the agent reads its credentials from a local file inside its container. The repository holds only
  placeholders.
- **Local models only:** the model runs on the host. No cloud provider is configured.
- **Dashboard and API:** both require credentials and are reachable only from the lab network.
- **Agent policy:** the agent's operating rules are a private file, mounted read-only. See
  [SECURITY.md](SECURITY.md#agent-policy).
