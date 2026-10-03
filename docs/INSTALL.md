# Installation Guide (VirtualBox + Rocky Linux 9)

This guide runs the entire cv-hermes stack **inside a dedicated VirtualBox VM** running Rocky Linux
9, using the same NAT + Host-only adapter pattern as this workspace's other lab
([`ai-cybersecurity-devops-lab`](../ai-cybersecurity-devops-lab)) — one adapter for internet access
(Discord, package installs, optionally a cloud LLM API), one private host-only link to reach LM
Studio running on the Windows host. Any hypervisor in the main [README.md](../README.md)'s spec
table works in principle, but the network-adapter and port-forwarding steps below are
VirtualBox-specific.

## Why Rocky Linux 9

Free, no registration, RHEL-compatible — the same `dnf`-based commands in
`scripts/00_setup_rocky9_host.sh` apply directly, and it's what the rest of this workspace's labs
target first.

## 1. Install VirtualBox on the Windows host

Download from virtualbox.org and install normally. The Extension Pack isn't required for this lab.

## 2. Create (or reuse) the host-only network

If `ai-cybersecurity-devops-lab` is already set up on this machine, its host-only network already
exists — reuse it rather than creating a second one. Otherwise:

1. **File → Tools → Network Manager** (or **Host Network Manager** on older VirtualBox versions).
2. Create a new **Host-only Network** if none exists (default name `vboxnet0`).
3. Note its IPv4 address — default `192.168.56.1`. This is the Windows host's address as seen from
   the VM, and the default this project's `.env.example`/`HOST_LM_STUDIO_IP` and
   `scripts/00_setup_rocky9_host.sh`'s `LOCAL_SUBNET` assume. If yours differs, use that value
   everywhere `192.168.56.1`/`192.168.56.0/24` appears below.
4. Leave its DHCP server enabled so the VM gets an IP automatically.

## 3. Create the Rocky 9 VM

Sizing per the main README's spec table:

- **Type/Version:** Linux / Red Hat (64-bit)
- **RAM:** 8192 MB (8 GB minimum, 16 GB+ recommended)
- **CPU:** 4 cores minimum, 8 recommended
- **Disk:** 50 GB, dynamically allocated (VDI)

**Network adapters (Settings → Network):**
- **Adapter 1: NAT** — internet access for package installs (`dnf`, `docker pull`) and for
  hermes-agent's own outbound traffic to Discord (and a cloud LLM API, if you use one instead of a
  local model).
- **Adapter 2: Host-only Adapter** → select the network from step 2 — this is how the VM reaches LM
  Studio on Windows.

Set both adapters' **Adapter Type** to **Paravirtualized Network (virtio-net)** for better
performance — Rocky 9 has virtio drivers built in.

Attach the Rocky 9 minimal ISO (**Settings → Storage**), boot with **Normal Start** so you get a
console to watch the installer, and run through it — a minimal install (no desktop environment) is
enough. The installer's mouse pointer is inaccurate until Guest Additions are installed; navigate
with the keyboard (`Tab`/`Space`/`Enter`/arrows) instead.

## 4. Set up SSH port forwarding (Windows → VM)

**Settings → Network → Adapter 1 (NAT) → Advanced → Port Forwarding:**

| Name | Protocol | Host IP | Host Port | Guest IP | Guest Port |
|---|---|---|---|---|---|
| ssh | TCP | 127.0.0.1 | 2223 | (blank) | 22 |

Host port **2223**, not **2222** — `ai-cybersecurity-devops-lab`'s VM already forwards `2222` to its
own SSH; using a different port here lets both VMs run at the same time without a conflict
(`ssh -p 2223 <user>@127.0.0.1` reaches this one, `ssh -p 2222 <user>@127.0.0.1` reaches the other).

**No Grafana port-forward rule** — deliberately. `ai-cybersecurity-devops-lab`'s install guide
documents a confirmed VirtualBox NAT engine ("slirp") bug where certain HTTP responses through a
NAT port-forward hang indefinitely; that project works around it by reaching its dashboard via the
VM's host-only IP instead of a NAT-forwarded port, and this project uses the same approach for
Grafana — see step 9.

## 5. Inside the VM: install Docker Engine and get the project

```bash
git clone https://github.com/cv-ai-sec/cv-hermes.git
cd cv-hermes
```

If you haven't pushed yet, use `scp` from Windows over the SSH port-forward instead:
```powershell
scp -P 2223 -r "D:\Ai projects\Projects\cv-hermes" <user>@127.0.0.1:~/
```

## 6. Run the host provisioning script

Open `scripts/00_setup_rocky9_host.sh` first and check the variables at the top — `LOCAL_SUBNET`
defaults to `192.168.56.0/24` (the host-only subnet from step 2), `GRAFANA_PORT` defaults to `3000`,
`TASK_DASHBOARD_PORT` defaults to `8502`, and `WEB_CHAT_PORT` defaults to `8503`; only change these
if your host-only network uses a different range, or a default port is unavailable for some other
reason.

```bash
sudo bash scripts/00_setup_rocky9_host.sh
```

This installs Docker CE + the Compose plugin, `git`, configures `firewalld` (SSH + Grafana + the
task dashboard + the local web chat UI, all from `LOCAL_SUBNET` only + blocks `obs-net`'s egress
entirely), and sets the SELinux boolean containers need under enforcing mode.

**Already provisioned this VM before the task dashboard/web chat existed?** The script is safe to
re-run in full (its `firewall-cmd` calls are idempotent), or apply just the new rules by hand:
```bash
sudo firewall-cmd --permanent --zone=public --add-rich-rule="rule family='ipv4' source address='192.168.56.0/24' port port='8502' protocol='tcp' accept"
sudo firewall-cmd --permanent --zone=public --remove-port='8502/tcp' 2>/dev/null || true
sudo firewall-cmd --permanent --zone=public --add-rich-rule="rule family='ipv4' source address='192.168.56.0/24' port port='8503' protocol='tcp' accept"
sudo firewall-cmd --permanent --zone=public --remove-port='8503/tcp' 2>/dev/null || true
sudo firewall-cmd --reload
```
(swap in your actual `LOCAL_SUBNET`/ports if you changed the defaults) — and record the change in
`Projects\firewall-audit-log\CHANGELOG.md` per this workspace's standing convention.

Log out and back in (or `newgrp docker`) so your user's new `docker` group membership takes effect:

```bash
newgrp docker
docker run --rm hello-world
```

## 7. Install LM Studio on the Windows host (not inside the VM)

Skip this step if you're pointing `LLM_API_BASE` at a cloud provider instead.

1. Download and install LM Studio normally on Windows.
2. Download an open-weight model (`.env.example` defaults to `qwen2.5-7b-instruct` — adjust
   `LLM_MODEL` in `.env` to match whatever model ID LM Studio reports).
3. Go to LM Studio's **Developer** tab and start the local server.
4. Enable **"Serve on Local Network"** so it binds to `0.0.0.0:1234` instead of `127.0.0.1` (the VM
   can't reach a literal loopback bind on the Windows host).
5. **Lock this down in Windows Firewall** immediately, so it's reachable only from the VM's
   host-only subnet:
   ```powershell
   New-NetFirewallRule -DisplayName "LM Studio - VM only" -Direction Inbound -Protocol TCP `
     -LocalPort 1234 -RemoteAddress 192.168.56.0/24 -Action Allow
   ```
   (Run as Administrator. Adjust `192.168.56.0/24` if your host-only network uses a different
   range. Skip this if you already added it for `ai-cybersecurity-devops-lab` — one rule covers
   both, since both VMs sit on the same host-only subnet.)

   **Don't also add a second "block everyone else" rule.** An earlier version of this guide did,
   and it caused a real, hard-to-diagnose outage: Windows Firewall gives Block rules precedence
   over Allow rules whenever both match the same traffic, regardless of specificity — so a
   `Block` rule scoped to `RemoteAddress Any` also matches (and silently defeats) the `Allow` rule
   above, since `Any` includes `192.168.56.0/24` too. The single Allow rule is sufficient on its
   own: Windows Firewall already denies everything not explicitly allowed. Full incident writeup
   in this workspace's local-only `Projects\firewall-audit-log\CHANGELOG.md`.

## 8. Configure environment and bring up the stack

```bash
cp .env.example .env
```

Edit `.env` and fill in `DISCORD_TOKEN`/`DISCORD_APPLICATION_ID` (from the
[Discord Developer Portal](https://discord.com/developers/applications)). Leave `REVOLT_TOKEN`
blank — Revolt is scaffolded but not currently functional (a dependency conflict, see
`hermes_agent/requirements.txt`); setting it without the package installed fails with a clear error
rather than running. Confirm `HOST_LM_STUDIO_IP` matches your host-only adapter's IP (check with
`ip addr show | grep 192.168.56` inside the VM), and change `GRAFANA_ADMIN_PASSWORD` from its
placeholder.

`docker-compose.yml` lives at the repo root here (unlike `ai-cybersecurity-devops-lab`, which keeps
it in a `docker/` subfolder) — so a plain `docker compose` from the repo root picks up both the
compose file and `.env` automatically:

```bash
docker compose up -d
docker compose ps
```

## 9. Verify network isolation

Confirm `obs-net` (Loki/Promtail/Grafana) genuinely cannot reach the internet — this should time
out, not succeed:

```bash
docker compose exec grafana curl -m 3 -sS https://8.8.8.8
```

Confirm hermes-agent can reach LM Studio on the Windows host (skip if using a cloud LLM API):

```bash
docker compose exec hermes-agent curl -m 3 -sS http://host.docker.internal:1234/v1/models
```

## 10. Access Grafana

Find the VM's host-only IP:

```bash
ip addr show | grep 192.168.56
```

Then from Windows, visit `http://<that-ip>:<GRAFANA_PORT>` (e.g. `http://192.168.56.102:3000` —
yours may differ; DHCP-assigned host-only IPs are usually stable across reboots but not guaranteed).
Log in with `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD` from `.env`. The **Hermes Agent Overview**
dashboard is auto-provisioned.

## Troubleshooting

- **`docker run --rm hello-world` fails with "permission denied ... docker.sock":** your shell
  session predates the `usermod -aG docker` group change the setup script made. Run `newgrp docker`
  (or log out/back in over SSH) rather than re-running the script.
- **`git clone`/`scp` fails with "Permission denied" creating the work tree dir:** you're likely in
  a root-owned directory. `cd ~` first.
- **`hermes-agent` can't reach LM Studio (`curl` in step 9 fails/times out):** confirm LM Studio's
  server is running with "Serve on Local Network" enabled (step 7.4), the Windows Firewall rule
  allows the host-only subnet (step 7.5), and `HOST_LM_STUDIO_IP` in `.env` matches the host-only
  adapter's actual IP — then recreate the container so the `extra_hosts` mapping picks up the
  change: `docker compose up -d --force-recreate hermes-agent`.
- **Grafana shows "no data" on every panel:** check Promtail is actually shipping lines —
  `docker compose logs promtail` — and that `hermes-agent` has written anything to
  `/var/log/hermes/hermes.jsonl` yet (`docker compose exec hermes-agent cat /var/log/hermes/hermes.jsonl`).
  If the file is empty, send the bot a message in Discord first, then check again. If lines exist
  but panels are still empty, validate the schema:
  `docker compose exec hermes-agent python -m scripts.parse_metrics /var/log/hermes/hermes.jsonl`.
- **Bot never responds in Discord, no errors in logs:** confirm the bot has "Message Content
  Intent" enabled in the Discord Developer Portal (**Bot → Privileged Gateway Intents**) — without
  it, `discord.py` silently receives messages with empty `content`.
- **`hermes-agent` fails to start with a permission error writing to `/app/notes` or `/app/data`:**
  the bind-mounted host directories (`./notes`, `./data`) need to be writable by the container's
  non-root UID (`10001`). If `docker compose up` created them as root on first run, fix ownership:
  `sudo chown -R 10001:10001 notes data workspace` (the same issue can affect `./workspace` for the
  same reason).
- **`summarize <url>` replies `[Task Failed] No 'en' transcript/captions available`:** this is
  expected for audio-only videos or ones without English captions — Whisper-based transcription for
  that case isn't implemented yet (see `docs/ARCHITECTURE.md`). Try a video with existing captions to
  confirm the pipeline itself works.
- **`summarize <url>` replies the generic `[Task Failed] Could not fetch transcript`** (not the
  specific "no transcript" message above), and `docker compose logs hermes-agent` shows a `yt-dlp`
  error like `Requested format is not available`: this is `yt-dlp` itself being out of date against
  YouTube's current extraction internals, unrelated to this project's own code — confirmed live, not
  hypothetical (`requirements.txt` deliberately leaves `yt-dlp` unpinned for exactly this reason).
  Force a fresh install of the latest release:
  ```bash
  docker compose build --no-cache hermes-agent
  docker compose up -d
  ```
- **`summarize <url>` replies `[Task #N Failed] Note generation failed`**, and the logs show an
  `exceeds the available context size` error from the LLM: the video's transcript is longer than
  the loaded model's context window can handle alongside the note-generation prompt and response.
  Two fixes, not mutually exclusive:
  1. `NotesService` already truncates transcripts to `MAX_TRANSCRIPT_CHARS` (default `20000`) to
     avoid this — if it still happens, your loaded model's context window is smaller than the
     default assumes; lower `MAX_TRANSCRIPT_CHARS` in `.env`, or
  2. increase the model's actual context window in LM Studio (**Developer tab → the loaded
     model's settings → Context Length**) if your hardware/model supports more than 8K, then raise
     `MAX_TRANSCRIPT_CHARS` to match. Either way, a truncated transcript produces a note covering
     only the start of the video, not a silent failure — the generated `.md` file says so explicitly
     when it happens.
- **Can't reach Grafana from Windows at all:** confirm you're using the VM's host-only IP (step 10),
  not `127.0.0.1` — there's no NAT port-forward for Grafana by design (step 4). Also re-check
  `sudo firewall-cmd --list-rich-rules` on the VM includes the Grafana allow rule for your actual
  `LOCAL_SUBNET`.
- **SSH (`ssh -p 2223 ...`) fails with `kex_exchange_identification: read: Connection reset`:** the
  TCP connection succeeded but nothing spoke SSH back — check the port-forward rule's guest port is
  `22` (not `2223`), confirm `sudo systemctl status sshd` is active inside the VM.
- **SELinux denials in `/var/log/audit/audit.log` when a container tries to read a mounted
  config/volume:** confirm the volume's compose entry still has its `:Z` suffix (e.g.
  `./workspace:/workspace:Z`) — removing it is the most common way this regresses.
