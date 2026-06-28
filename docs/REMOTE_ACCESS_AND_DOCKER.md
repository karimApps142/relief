# Remote access (SSH Mac → Windows) + Docker

Two operational guides for the GPU box (`DESKTOP-BVI0N3I`, Windows 11 Pro, RTX 3060 12 GB):

- **Part A** — SSH from the MacBook so you drive the Windows box from your Mac terminal (git pull,
  start the app, run inference) and view the UI locally over a tunnel. This is how you "handle
  most of it from the Mac."
- **Part B** — Docker, for cloning the setup onto the _other_ Windows machines once native works.

---

## ⚡ Quick start — connect & run (the everyday commands)

**1. On the Mac** (Terminal) — SSH into the box over Tailscale:

```bash
ssh ad@100.86.189.84
cd /d F:\relief
```

**2. On the box** — pull latest + start the app:

```
cd /d F:\relief
git pull
.venv\Scripts\python.exe app_gradio.py
```

Wait for `Running on http://0.0.0.0:7860`.

**3. View it on the Mac** — open in the browser (no tunnel needed; Tailscale routes directly):

> **http://100.86.189.84:7860**

**Stop:** `Ctrl+C` in that terminal, then `exit` to leave SSH.

Notes:

- Keep the SSH terminal open — closing it stops the app.
- If `ssh` asks for a password, enter the Windows **`ad`** account password.
- `connection refused / timed out` → the box is off/asleep or not on Tailscale; power it on.
- First **Generate** with the **sapiens** depth model downloads ~4 GB once (cached after).
- Box identity: `DESKTOP-BVI0N3I`, Tailscale IP `100.86.189.84`, project at `F:\relief`.

---

# Part A — SSH into Windows from the Mac

## A1. Enable OpenSSH Server on Windows (one-time)

Open **PowerShell as Administrator** on the Windows box:

```powershell
# install the OpenSSH server feature
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0

# start it now + on every boot
Start-Service sshd
Set-Service -Name sshd -StartupType Automatic

# make sure the firewall allows port 22 (installer usually adds this; this is a safe re-run)
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True `
  -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 -ErrorAction SilentlyContinue

# (recommended) make PowerShell the shell you get over SSH instead of cmd.exe
New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell `
  -Value "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -PropertyType String -Force
```

Find your Windows username and IP (you'll need both from the Mac):

```powershell
whoami        # e.g. desktop-bvi0n3i\karim   -> the part after \ is your <win-user>
ipconfig      # note the IPv4 Address, e.g. 192.168.1.50  -> your <win-ip>
```

> Tip: give the box a **DHCP reservation** in your router (or a static IP) so `<win-ip>` doesn't
> change. Or use Tailscale (A6) for a stable name that works off-LAN too.

## A2. First login from the Mac (password, to confirm it works)

```bash
ssh <win-user>@<win-ip>
# type the Windows account password -> you should land in a PowerShell prompt
exit
```

## A3. Key-based login (no more passwords)

On the **Mac**, make a dedicated key (or reuse an existing one like
`~/.ssh/id_ed25519_karimapps142`):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/winbox -C "mac->winbox"   # press enter twice (or set a passphrase)
cat ~/.ssh/winbox.pub                                      # copy this whole line
```

Now install that public key on Windows. **Which file depends on whether the account is an
Administrator** — this is the #1 thing people get wrong:

**If `<win-user>` is a standard (non-admin) user** — PowerShell on Windows:

```powershell
mkdir $env:USERPROFILE\.ssh -Force
Add-Content $env:USERPROFILE\.ssh\authorized_keys "PASTE_THE_PUB_KEY_LINE_HERE"
```

**If `<win-user>` is an Administrator** (common on a personal PC) — sshd ignores the per-user file
and uses a shared file that needs locked-down permissions:

```powershell
Add-Content C:\ProgramData\ssh\administrators_authorized_keys "PASTE_THE_PUB_KEY_LINE_HERE"
# fix permissions or sshd silently rejects the key:
icacls.exe C:\ProgramData\ssh\administrators_authorized_keys /inheritance:r `
  /grant "Administrators:F" /grant "SYSTEM:F"
```

Test from the Mac:

```bash
ssh -i ~/.ssh/winbox <win-user>@<win-ip>      # should log in with NO password
```

> If it still asks for a password: you almost certainly hit the admin-vs-user file split above, or
> the `icacls` permissions. Re-check those two.

## A4. A short alias on the Mac

Add to `~/.ssh/config` on the Mac:

```sshconfig
Host winbox
    HostName 192.168.1.50        # your <win-ip>
    User <win-user>
    IdentityFile ~/.ssh/winbox
```

Now it's just:

```bash
ssh winbox
```

## A5. The workflow — drive the GPU box from the Mac

**Run commands remotely** (edit on Mac → push → pull + run on Windows, all from one terminal):

```bash
ssh winbox
# now on Windows:
cd Desktop\relief
git pull
.venv\Scripts\Activate.ps1
python app_gradio.py            # or: uvicorn service:app --host 0.0.0.0 --port 8000
```

**See the UI on the Mac** via an SSH tunnel — forward the Windows port back to the Mac so you open
it in your _Mac_ browser:

```bash
# Mac terminal: tunnel 7860 (Gradio) — keep this open
ssh -L 7860:localhost:7860 winbox
# in that session, start the app:  cd Desktop\relief; .venv\Scripts\Activate.ps1; python app_gradio.py
```

Then browse to **http://localhost:7860 on the Mac** — it's the 3060 doing the work, displayed
locally. (For the API instead, tunnel `-L 8000:localhost:8000` and start uvicorn.)

**One-shot remote command** (no interactive session):

```bash
ssh winbox "cd Desktop\relief; git pull"
```

This is the "most of it from the Mac" setup: code + git + launching all happen from your Mac; only
the GPU inference runs on the Windows box, and you view the result through the tunnel.

## A6. (Optional) Tailscale — stable name, works off your LAN

If the Mac and Windows box aren't always on the same network (or the IP keeps changing), install
**Tailscale** on both (free, 2 min). You get a fixed name like `desktop-bvi0n3i` you can SSH to
from anywhere: `ssh <win-user>@desktop-bvi0n3i`. Replace `HostName` in `~/.ssh/config` with the
Tailscale name. Everything else above is unchanged.

---

# Part B — Docker on Windows 11

## B1. When to bother

**Get the native run working first** (`WINDOWS_SETUP.md`). Docker's value is **reproducing the
torch/CUDA stack across the _other_ Windows machines** without re-fighting the install — not
debugging the first box. So: native here → confirm real output → then containerize for the fleet.
Docker removes the _Python-dependency_ pain, **not** the GPU-driver setup — every machine still
needs the NVIDIA driver + WSL2.

> Don't bother on the Mac — Docker on Apple Silicon can't reach an NVIDIA GPU.

## B2. Prerequisites (per Windows machine)

1. Latest **NVIDIA driver** (you already have this for native).
2. **WSL2**: in an admin PowerShell, `wsl --install` (Windows 11 installs WSL2 + a Linux distro in
   one step), then reboot.
3. **Docker Desktop** with the **WSL2 backend** (Settings → General → "Use the WSL 2 based
   engine"). Recent Docker Desktop wires NVIDIA GPU passthrough through WSL2 automatically.

## B3. Verify the GPU is visible to Docker

```powershell
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
# should print the RTX 3060 table
```

If that fails, fix it before building — it's the driver/WSL2 layer, not the image.

## B4. Build + run (with a persistent weights volume)

From the repo folder (it has the `Dockerfile`):

```powershell
docker build -t relief-gpu .

docker run --gpus all -p 8000:8000 `
  -v hf_cache:/root/.cache/huggingface `
  relief-gpu
```

- `--gpus all` gives the container the 3060.
- `-v hf_cache:/root/.cache/huggingface` **persists the downloaded weights** across container
  restarts — without it every `docker run` re-downloads several GB. Trigger the download once
  (`POST /models/download`); the volume keeps them.

## B5. API vs UI in the container

The `Dockerfile` runs **`uvicorn service:app` on port 8000** — the JSON API
(`/relief`, `/models/status`, `/models/download`), **not** the Gradio UI. So with the container
running you'd:

```powershell
curl.exe -X POST http://localhost:8000/models/download      # once
curl.exe -F "file=@img.jpg" -F "backend=auto" http://localhost:8000/relief
```

Want the **Gradio UI from the container too**? Cleanest is to mount it onto the same FastAPI app so
one container serves both at `:8000` (API) and `:8000/ui` (UI). Add to `service.py`:

```python
import gradio as gr
from app_gradio import demo
app = gr.mount_gradio_app(app, demo, path="/ui")
```

Rebuild, and the UI is at `http://localhost:8000/ui`. (Ask me and I'll wire this in.)

## B6. Deploy to the other Windows machines

1. On each box: NVIDIA driver + WSL2 + Docker Desktop (B2) once.
2. Either `docker build` from the repo, or push `relief-gpu` to a registry and `docker pull`.
3. `docker run --gpus all -p 8000:8000 -v hf_cache:/root/.cache/huggingface relief-gpu`.
4. Hit **Download Models** once per machine (or pre-seed the `hf_cache` volume).

See [`parts/part-08-docker.md`](parts/part-08-docker.md) for the same content in the build-parts
format.
