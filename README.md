# cv-hermes

A cybersecurity learning lab built on the official **Hermes Agent** by Nous Research. It runs the agent's
official container image with its recommended settings, and adds the lab pieces around it: a restricted
network, a Discord interface, a local model, and dashboards for observing the agent.

- Hermes Agent (official project): **[hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/)**
- Hermes quickstart: **[quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)**

## Focus

The lab focuses on the **OWASP Top 10 for LLM Applications** (2025): prompt injection, sensitive information
disclosure, supply chain, data and model poisoning, improper output handling, excessive agency, system prompt
leakage, vector and embedding weaknesses, misinformation and overreliance, and unbounded consumption.
The classic web OWASP Top 10 is out of scope.

A planned addition is detection of unauthorized entities on the lab network, such as rogue MCP servers and
unknown agents. It is designed but not built.

## What runs

- The agent, in its official container, with a dashboard and an API. Both require credentials and are reachable
  only from the lab network.
- An egress proxy. It is the agent's only route to the internet, and it allows a short list of hosts.
- A local language model served by LM Studio on the host machine. No cloud model provider is used.
- Grafana and Loki for observing the agent's logs. They have no internet route.

This is **not** an air-gapped environment. The agent reaches two outside hosts through the proxy.
The security rules and accepted risks are in [docs/SECURITY.md](docs/SECURITY.md).

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md): one-time setup
- [docs/USER-GUIDE.md](docs/USER-GUIDE.md): day-to-day operation
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): how the pieces connect
- [docs/SECURITY.md](docs/SECURITY.md): rules and accepted risks

## Secrets and addresses

Real values, addresses, and credentials never go in this repository. Configuration files hold placeholders only.
The live values are kept in local, git-ignored files on the machine that runs the lab.
