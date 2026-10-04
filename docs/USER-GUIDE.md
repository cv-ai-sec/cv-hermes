# User Guide

Day-to-day operation of a stack that's already set up. For first-time setup, see [INSTALL.md](INSTALL.md).
Built on the official [Hermes Agent](https://hermes-agent.nousresearch.com/)
([quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)).

Placeholders in angle brackets, such as `<VM address>`, stand for the values kept in local documentation.

## Reaching the services

Only machines on the lab network can reach these. Look up the VM's address on the VM with `ip -4 addr show`.

| Service | How to reach it | Login |
|---|---|---|
| Hermes dashboard | Browser, `<VM address>` on the dashboard port | Dashboard credentials in the agent's local environment file |
| Hermes API | HTTP, `<VM address>` on the API port | Bearer key in the agent's local environment file |
| Grafana | Browser, `<VM address>` on the Grafana port | Grafana admin credentials in the local compose environment file |
| Shell access to the VM | SSH to the forwarded port on the host | Your VM account password |

## Start the stack

Order matters: model server first, then the VM, then the containers.

1. **Host:** start LM Studio and load the model. Confirm its server is running.
2. **Host:** start the VM.
3. **VM:** wait about a minute, then check:
   ```bash
   cd ~/cv-hermes
   docker compose ps
   sudo systemctl status hermes-egress.service --no-pager
   ```
   Every container should show `Up`, and the egress service `active (exited)`. If a container is missing, run
   `docker compose up -d`.

The egress rules are applied at boot by a system service, so no manual firewall step is needed.

## Stop the stack

Routine stop (keeps everything for next time):
```bash
docker compose stop
sudo shutdown -h now
```

Use `sudo shutdown -h now` over SSH. Don't use the hypervisor's power-off for a routine stop, since that can
corrupt the agent's database. A hard power-off is a last resort for a hung VM only.

Full teardown (removes containers and networks, keeps named volumes and the agent's data):
```bash
docker compose down
```

## Checks

```bash
docker exec hermes-agent hermes status          # model server, chat platform, gateway state
docker compose logs --tail 20 hermes-agent      # recent agent output
docker compose logs --tail 20 egress-proxy      # proxy health
```

Chat test through the API (should reply with `ok`):
```bash
docker exec hermes-agent sh -c 'K=$(grep "^API_SERVER_KEY=" /opt/data/.env | cut -d= -f2); curl -s -m 120 -H "Authorization: Bearer $K" -H "Content-Type: application/json" -d "{\"model\":\"<model id>\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word ok.\"}]}" http://127.0.0.1:8642/v1/chat/completions'
```

Egress checks. A direct request to a non-allowlisted host must fail. The chat platform must still be reachable
through the proxy:
```bash
docker exec hermes-agent curl --noproxy '*' -m 5 -sS https://example.com -o /dev/null; echo rc=$?
docker exec hermes-agent sh -c 'curl -x "$HTTPS_PROXY" -m 10 -sS https://discord.com/api/v10/gateway -o /dev/null -w "%{http_code}\n"'
```

## Common operations

| Task | Command |
|---|---|
| Restart the agent (keeps environment) | `docker compose restart hermes-agent` |
| Apply changes to compose or environment files | `docker compose up -d <service>` (a restart does not reload them) |
| Follow agent logs | `docker compose logs -f hermes-agent` |
| Check the boot-time firewall rules | `sudo iptables -L DOCKER-USER -n --line-numbers` |
| Change the chat platform token | Edit the agent's environment file with `sudo`, then restart the agent |

## Troubleshooting

- **Slow responses:** check the model's memory settings in LM Studio. See the local model section of
  [INSTALL.md](INSTALL.md).
- **Context window below the required minimum:** the agent refuses to run. Reload the model with a larger
  context setting.
- **Chat platform won't connect:** the token is wrong or was reset. Generate a new one in the platform's
  developer console.
- **No agent logs in Grafana:** check the log shipper's output for permission errors, then check that the log
  store has the agent's job.
