# cv-hermes

A cybersecurity learning lab built on the official **Hermes Agent** by Nous Research. It runs the agent's
official container image with its recommended settings, and adds the lab pieces around it: a restricted
network, a chat interface, a local model, and dashboards for observing the agent.

- Hermes Agent (official project): **[hermes-agent.nousresearch.com](https://hermes-agent.nousresearch.com/)**
- Hermes quickstart: **[quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)**

## Learning use

This repository is for learning. You can give its public material to a coding agent, such as Claude Code, to help
you build your own version. Give the agent the public docs and your own configuration only. The restricted
configuration isn't in this repository, so the agent works from the outline in [docs/INSTALL.md](docs/INSTALL.md) and
the controls in [docs/SECURITY.md](docs/SECURITY.md). Keep real credentials and addresses out of the agent's context.
If you build your own version, consider setting up a secure, private way to export any restricted files it needs.

## Focus

The lab focuses on the **OWASP Top 10 for LLM Applications** (2025): prompt injection, sensitive information
disclosure, supply chain, data and model poisoning, improper output handling, excessive agency, system prompt
leakage, vector and embedding weaknesses, misinformation and overreliance, and unbounded consumption.
The classic web OWASP Top 10 is out of scope.

## Role

The agent is a learning companion for the labs. It explains findings and simulations, answers questions about
the lab, and guides you through each exercise. Every action it takes goes through you.

If the agent is given a work role such as email triage, notes boards, or project and knowledge management, that role
is **draft and label only**: a person approves every change, and instructions found inside messages or pages are
treated as data, never as orders. The rules are in
[docs/SECURITY.md](docs/SECURITY.md#work-integrations-email-and-notes-boards).

## What runs

- The agent, in its official container, with a dashboard and an API. Both require credentials and are reachable
  only from the lab network.
- An egress proxy. It is the agent's only route to the internet, and it allows a short list of hosts.
- A local language model served by a local model server on the host machine. No cloud model provider is used.
- Grafana and Loki for observing the agent's logs. They have no internet route.

Outbound access is limited to a short allowlist through the proxy. The security rules are in
[docs/SECURITY.md](docs/SECURITY.md).

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md): setup outline (step-by-step details are private)
- [docs/USER-GUIDE.md](docs/USER-GUIDE.md): day-to-day operation (generic; stack commands are private)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): components and trust boundaries
- [docs/SECURITY.md](docs/SECURITY.md): rules, controls, buildout rules, and how to review them

Configuration files for the network, host, and monitoring stack are not published. See
[docs/SECURITY.md](docs/SECURITY.md#buildout-and-configuration).

## Secrets and addresses

Real values, addresses, and credentials never go in this repository. Configuration files hold placeholders only.
The live values are kept in local, git-ignored files on the machine that runs the lab.
