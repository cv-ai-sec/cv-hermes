# User Guide

Day-to-day reference for a running stack. This guide is generic on purpose. The stack-specific commands, addresses,
and checks are in the operator's private runbook, and the rules for what goes where are in
[SECURITY.md](SECURITY.md).

Placeholders in angle brackets, such as `<host address>`, stand for values kept in local, private documentation.

## Reaching the services

Services are reachable only from the lab network. The addresses and ports are set in the local environment file on
the machine that runs the lab, not in this repository.

| Service | How to reach it | Login |
|---|---|---|
| Agent dashboard | Browser, on the lab network | Dashboard credentials from the agent's local environment file |
| Agent API | HTTP, on the lab network | Bearer key from the agent's local environment file |
| Log dashboards | Browser, on the lab network | Admin credentials from the local environment file |
| Host shell | SSH, on the lab network | Account credentials held by the operator |

## Start the stack

Start in this order: the local model server first, then the host virtual machine, then the containers. Confirm each
step before the next. Each container should report a healthy, running state. Stack-specific checks are in the
operator's runbook.

## Stop the stack

**Routine stop**, which keeps all data for next time: stop the containers gracefully, then shut the host down with
its normal shutdown command, not a forced power-off.

**Full teardown**, which removes containers and networks and keeps named data: use the container tool's down command.

A forced power-off or a hard kill can interrupt a write to the agent's data. Use it only for a machine that won't
respond to a normal shutdown.

**Emergency stop of the agent only**, with the rest running, is described in [SECURITY.md](SECURITY.md#incident-response).
The stop procedure for this deployment is kept in the operator's restricted runbook.

## Checks

- The agent reports its model server, chat platform, and gateway state through its own status command.
- Recent agent output is available from the container logs.
- The API answers a short test request with a reply.
- Requests to disallowed destinations fail, and allowed chat traffic still works.

The exact commands for these checks are in the operator's restricted runbook.

## Common operations

| Task | How |
|---|---|
| Restart the agent, keeping its environment | Restart its container |
| Apply changes to configuration or environment files | Recreate the affected container. A restart does not reload them. |
| Follow agent logs | Stream its container logs |
| Change the chat platform token | Edit the agent's environment file with elevated rights, then restart the agent |

## Troubleshooting

- **Slow responses:** check the model's memory settings in the local model server.
- **Context window below the required minimum:** the agent refuses to run. Reload the model with a larger context.
- **Chat platform won't connect:** the token is wrong or was reset. Generate a new one in the platform's developer console.
- **No agent logs in the dashboards:** check the log shipper for permission errors, then check that the log store
  has the agent's data source.
