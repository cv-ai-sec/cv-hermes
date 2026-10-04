# User Guide

Day-to-day reference for a stack that's already set up. For first-time setup, see [INSTALL.md](INSTALL.md).
Built on the official [Hermes Agent](https://hermes-agent.nousresearch.com/)
([quickstart](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart)).

## Addresses

The VM's host-only address is DHCP-assigned. Find it on the VM with `ip -4 addr show` (the `enp0s8`
address). Real addresses are recorded locally in `Projects\system-audit-log\CV-HERMES-SERVICES.md`.

| What | Address | Login |
|---|---|---|
| Hermes dashboard | `http://<VM host-only IP>:9119` | `HERMES_DASHBOARD_BASIC_AUTH_*` in `hermes-data/.env` |
| Hermes API | `http://<VM host-only IP>:8642` | Bearer key `API_SERVER_KEY` in `hermes-data/.env` |
| Grafana | `http://<VM host-only IP>:3000` | `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` in `.env` |
| SSH to the VM | `ssh -p 2223 <user>@127.0.0.1` from Windows | Your VM password |

Only machines on the VirtualBox host-only network can reach these ports.

## Start the stack

Order matters: LM Studio first, then the VM, then the containers.

1. **Windows:** start LM Studio and load the model. Confirm the Developer tab shows the server running.
2. **Windows:** start the VM, from the VirtualBox window or with `VBoxManage startvm "hermes agent" --type headless`.
3. **VM:** wait about a minute, then check:
   ```bash
   cd ~/cv-hermes
   docker compose ps
   sudo systemctl status hermes-egress.service --no-pager
   ```
   Every container should show `Up`, and the egress service `active (exited)`. If a container is missing, run
   `docker compose up -d`.

The egress rules are applied at boot by `hermes-egress.service`, so no manual firewall step is needed.

## Stop the stack

Routine stop (keeps everything for next time):
```bash
docker compose stop
sudo shutdown -h now
```

Use `sudo shutdown -h now` over SSH. Don't use VirtualBox's power-off button for a routine stop: that can
corrupt the agent's SQLite state in `hermes-data/`. A hard power-off is a last resort for a hung VM only.

Full teardown (removes containers and networks, keeps named volumes and `hermes-data/`):
```bash
docker compose down
```

## Checks

```bash
docker exec hermes-agent hermes status          # LM Studio, Discord, gateway state
docker compose logs --tail 20 hermes-agent      # recent agent output
docker compose logs --tail 20 egress-proxy      # proxy health
```

Chat test through the API (should reply with `ok`):
```bash
docker exec hermes-agent sh -c 'K=$(grep "^API_SERVER_KEY=" /opt/data/.env | cut -d= -f2); curl -s -m 120 -H "Authorization: Bearer $K" -H "Content-Type: application/json" -d "{\"model\":\"qwen/qwen2.5-vl-7b\",\"messages\":[{\"role\":\"user\",\"content\":\"Reply with the word ok.\"}]}" http://127.0.0.1:8642/v1/chat/completions'
```

Egress checks (direct internet must fail; Discord through the proxy must return 200):
```bash
docker exec hermes-agent curl --noproxy '*' -m 5 -sS https://example.com -o /dev/null; echo rc=$?
docker exec hermes-agent curl -x http://172.28.10.2:3128 -m 10 -sS https://discord.com/api/v10/gateway -o /dev/null -w "discord %{http_code}\n"
```

## Common operations

| Task | Command |
|---|---|
| Restart the agent (keeps environment) | `docker compose restart hermes-agent` |
| Apply changes to compose or `.env` | `docker compose up -d <service>` (a restart does not reload them) |
| Tail agent logs | `docker compose logs -f hermes-agent` |
| Check the boot-time firewall rules | `sudo iptables -L DOCKER-USER -n --line-numbers` |
| Change the Discord token | Edit `hermes-data/.env` with `sudo nano`, then `docker compose restart hermes-agent` |

## Gotchas

- **Slow responses:** the model needs its KV cache settings from the audit log (`EXTERNAL-SERVICES.md`).
  Confirm them in LM Studio's load dialog after any reload.
- **Context below 64,000 tokens:** Hermes refuses to run. Reload the model in LM Studio with context 65536.
- **Discord won't log in:** the token in `hermes-data/.env` has been reset or is wrong. Regenerate it in the Developer Portal.
- **Grafana shows no agent data:** check `docker compose logs --tail 5 promtail`. Promtail should show no permission errors.
