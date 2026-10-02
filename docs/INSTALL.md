# Installation Guide (VirtualBox + Rocky Linux 9)

This guide runs the entire cv-hermes stack **inside a dedicated VirtualBox VM** running Rocky Linux
9. It assumes VirtualBox since that's what this workspace's other lab
([`ai-cybersecurity-devops-lab`](../ai-cybersecurity-devops-lab)) already uses — any of the
hypervisors listed in the main [README.md](../README.md)'s spec table work too, but the
network-adapter and port-forwarding steps below are VirtualBox-specific.

## Why Rocky Linux 9

Free, no registration, RHEL-compatible — the same `dnf`-based commands in
`scripts/00_setup_rocky9_host.sh` apply directly, and it's what the rest of this workspace's labs
target first.

## 1. Install VirtualBox on the Windows host

Download from virtualbox.org and install normally. The Extension Pack isn't required for this lab.

## 2. Create the Rocky 9 VM

Sizing per the main README's spec table:

- **Type/Version:** Linux / Red Hat (64-bit)
- **RAM:** 8192 MB (8 GB minimum, 16 GB+ recommended)
- **CPU:** 4 cores minimum, 8 recommended
- **Disk:** 50 GB, dynamically allocated (VDI)

**Network adapter (Settings → Network → Adapter 1): Bridged Adapter**, attached to your physical
NIC. This gives the VM its own LAN-reachable IP directly — simplest option, and it avoids a
confirmed VirtualBox NAT engine ("slirp") bug where certain HTTP responses through a NAT
port-forward hang indefinitely (hit while building `ai-cybersecurity-devops-lab`'s dashboard; see
that project's `docs/INSTALL.md` step 4 for the full story). Set **Adapter Type** to
**Paravirtualized Network (virtio-net)** for better performance — Rocky 9 has virtio drivers built
in.

> **Using NAT instead of Bridged?** It works, but you'll need an explicit port-forward rule for
> `GRAFANA_PORT` (**Settings → Network → Adapter 1 → Advanced → Port Forwarding**), and you may hit
> the slirp bug above on that forwarded port. Bridged avoids both problems.

> **Using a local LLM server on the Windows host (e.g. LM Studio, Ollama) instead of a cloud API?**
> Add a second adapter as a **Host-only Adapter** (create one via **File → Tools → Network
> Manager** if none exists) — this is the same pattern `ai-cybersecurity-devops-lab` uses to reach
> LM Studio from its VM; see that project's `docs/INSTALL.md` steps 2 and 9 for the full setup
> (including the Windows Firewall rule to scope LM Studio's reachability to just this VM). Point
> `LLM_API_BASE` in `.env` at the host-only adapter's host-side IP (e.g.
> `http://192.168.56.1:1234/v1`).

Attach the Rocky 9 minimal ISO (**Settings → Storage**), boot with **Normal Start** so you get a
console to watch the installer, and run through it — a minimal install (no desktop environment) is
enough. The installer's mouse pointer is inaccurate until Guest Additions are installed; navigate
with the keyboard (`Tab`/`Space`/`Enter`/arrows) instead.

## 3. Find the VM's IP and confirm SSH

Once booted:

```bash
ip addr show   # note the IP on your bridged interface
sudo systemctl status sshd   # should be active by default on a minimal install
```

From Windows: `ssh <user>@<vm-ip>`.

## 4. Get the project into the VM

```bash
git clone https://github.com/cv-ai-sec/cv-hermes.git
cd cv-hermes
```

If you haven't pushed yet, use `scp` from Windows instead:
```powershell
scp -r "D:\Ai projects\Projects\cv-hermes" <user>@<vm-ip>:~/
```

## 5. Run the host provisioning script

Open `scripts/00_setup_rocky9_host.sh` first and check the two variables at the top:

- `LOCAL_SUBNET` — the subnet allowed to reach Grafana. With a bridged adapter, this is your real
  LAN subnet (e.g. `192.168.1.0/24`); check with `ip addr show` on the VM or your router's admin
  page.
- `GRAFANA_PORT` — only change this if `3000` conflicts with another project on the same VM (see
  the main README's "Running alongside other labs on the same VM" section).

Then run it:

```bash
sudo bash scripts/00_setup_rocky9_host.sh
```

This installs Docker CE + the Compose plugin, `git`, configures `firewalld` (SSH + Grafana from
`LOCAL_SUBNET` only + blocks `obs-net`'s egress entirely), and sets the SELinux boolean containers
need under enforcing mode.

Log out and back in (or `newgrp docker`) so your user's new `docker` group membership takes effect:

```bash
newgrp docker
docker run --rm hello-world
```

## 6. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in `DISCORD_TOKEN`/`DISCORD_APPLICATION_ID` (from the
[Discord Developer Portal](https://discord.com/developers/applications)), `LLM_API_BASE`/
`LLM_API_KEY`/`LLM_MODEL`, and change `GRAFANA_ADMIN_PASSWORD` from its placeholder.

## 7. Bring up the stack

`docker-compose.yml` lives at the repo root here (unlike `ai-cybersecurity-devops-lab`, which keeps
it in a `docker/` subfolder) — so a plain `docker compose` from the repo root picks up both the
compose file and `.env` automatically, no `-f`/`--env-file` flags needed:

```bash
docker compose up -d
docker compose ps
```

## 8. Verify network isolation

Confirm `obs-net` (Loki/Promtail/Grafana) genuinely cannot reach the internet — this should time
out, not succeed:

```bash
docker compose exec grafana curl -m 3 -sS https://8.8.8.8
```

Confirm hermes-agent *can* reach the internet (needed for Discord/LLM):

```bash
docker compose exec hermes-agent python -c "import urllib.request; print(urllib.request.urlopen('https://discord.com', timeout=5).status)"
```

## 9. Access Grafana

From a machine on `LOCAL_SUBNET`: `http://<VM_IP>:<GRAFANA_PORT>` (default `3000`). Log in with
`GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD` from `.env`. The **Hermes Agent Overview** dashboard
is auto-provisioned.

## Troubleshooting

- **`docker run --rm hello-world` fails with "permission denied ... docker.sock":** your shell
  session predates the `usermod -aG docker` group change the setup script made. Run `newgrp docker`
  (or log out/back in over SSH) rather than re-running the script.
- **`git clone`/`scp` fails with "Permission denied" creating the work tree dir:** you're likely in
  a root-owned directory. `cd ~` first.
- **Grafana shows "no data" on every panel:** check Promtail is actually shipping lines —
  `docker compose logs promtail` — and that `hermes-agent` has written anything to
  `/var/log/hermes/hermes.jsonl` yet (`docker compose exec hermes-agent cat /var/log/hermes/hermes.jsonl`).
  If the file is empty, send the bot a message in Discord first, then check again. If lines exist
  but panels are still empty, validate the schema:
  `docker compose exec hermes-agent python -m scripts.parse_metrics /var/log/hermes/hermes.jsonl`.
- **Bot never responds in Discord, no errors in logs:** confirm the bot has "Message Content
  Intent" enabled in the Discord Developer Portal (**Bot → Privileged Gateway Intents**) — without
  it, `discord.py` silently receives messages with empty `content`.
- **Browser can't reach `http://<VM_IP>:<GRAFANA_PORT>` from `LOCAL_SUBNET`, but `curl` from inside
  the VM works:** `firewalld`'s rich rule may not have applied — re-check
  `sudo firewall-cmd --list-rich-rules` on the VM includes the Grafana allow rule, and that your
  browser's actual source IP is really inside `LOCAL_SUBNET` (re-run the setup script after fixing
  `LOCAL_SUBNET` if it was wrong the first time — it's safe to re-run).
- **VM has no internet access at all (package installs/`docker pull` fail):** confirm the bridged
  adapter picked up a DHCP lease from your router (`ip addr show`) — a bridged adapter depends on
  your physical network's DHCP server, unlike NAT's built-in one.
- **SELinux denials in `/var/log/audit/audit.log` when a container tries to read a mounted
  config/volume:** confirm the volume's compose entry still has its `:Z` suffix (e.g.
  `./workspace:/workspace:Z`) — removing it is the most common way this regresses.
