# Deploy doctool with Docker

This guide shows you how to run doctool, with LibreOffice for the Office tools, in a single
container using Docker Compose, and what you must add before anyone else can reach it.

**Who this is for:** someone who wants doctool on a Linux server or in a container instead of a
local Python install.

> **Status: unverified.** The [Dockerfile](../Dockerfile) and
> [docker-compose.yml](../docker-compose.yml) are written but the image has **not been built or
> run yet**: Docker is not installed on the development machine. The Python test suite was run on
> Linux (WSL Ubuntu) without LibreOffice. Treat the first build as a test and report what fails.

> **doctool has no login.** Anyone who can reach the port can read, change and delete every
> document. The Compose file publishes the port on `127.0.0.1` only. Do **not** expose it to a
> network until a reverse proxy with authentication sits in front of it (see
> [Expose it beyond localhost](#4-expose-it-beyond-localhost)). [SPEC.md](SPEC.md) section 9 treats
> any LAN exposure as a security-critical change.

## Prerequisites

- Docker Engine with the Compose plugin (`docker compose`).
- About 2 GB of free memory for the container (the Compose limit).
- A clone of the repository; run every command from its root.

## What the image contains

The [Dockerfile](../Dockerfile) has two stages:

1. `node:22-slim` builds the web UI (`npm ci`, `npm run build`).
2. `python:3.12-slim` runs the API and serves the built UI. It installs:

| Package | Why |
|---|---|
| `libreoffice-core`, `-writer`, `-calc`, `-impress`, `-draw`, `-pdfimport` | Office to PDF, and PDF to Word "Keep the look" |
| `fonts-liberation` | Metric-compatible with Arial, Times New Roman, Courier New |
| `fonts-crosextra-carlito`, `fonts-crosextra-caladea` | Metric-compatible with Calibri and Cambria |
| `fonts-dejavu-core` | General fallback font |
| `tini` | Init process (PID 1) that reaps the helper processes LibreOffice starts |

The container runs as the non-root user `doctool` (uid 10001), with a health check on
`GET /api/v1/health`.

**Ghostscript is not in the image.** It is AGPL-licensed and doctool is Apache-2.0, so it is
not bundled. The Compress tool uses Pillow instead; no current tool needs Ghostscript.

### Environment set by the image

| Variable | Value in the image | Meaning |
|---|---|---|
| `DOCTOOL_DATA_DIR` | `/data` | Database, files and LibreOffice profile |
| `DOCTOOL_WEB_DIR` | `/app/web/dist` | Built UI |
| `DOCTOOL_HOST` | `0.0.0.0` | Bind inside the container |
| `DOCTOOL_ALLOW_LAN` | `1` | Required to bind anything other than `127.0.0.1`/`localhost` |
| `DOCTOOL_PORT` | `8000` | Port inside the container |
| `DOCTOOL_SOFFICE` | `/usr/bin/soffice` | LibreOffice program |
| `HOME` | `/data` | Keeps LibreOffice's home files on the writable volume |

`DOCTOOL_ALLOW_LAN=1` only lets the process bind `0.0.0.0` inside the container. What limits
exposure is the published port in Compose. The other `DOCTOOL_*` settings, including the
`DOCTOOL_OFFICE_*` limits, are listed in [office-setup.md](office-setup.md#4-settings).

## 1. Build and start

```bash
docker compose build
docker compose up -d
```

The [docker-compose.yml](../docker-compose.yml) service applies these protections:

| Setting | Value | Effect |
|---|---|---|
| `ports` | `127.0.0.1:8000:8000` | Reachable from this host only |
| `DOCTOOL_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Other `Host` headers are rejected (anti DNS-rebinding) |
| `read_only` | `true` | Root filesystem is read-only |
| `tmpfs` | `/tmp` | Writable scratch space in memory |
| `cap_drop` | `ALL` | No Linux capabilities |
| `security_opt` | `no-new-privileges:true` | No privilege gain through setuid binaries |
| `mem_limit` | `2g` | Bounds a hostile document's memory use |
| `cpus` | `2` | Bounds CPU use |
| `pids_limit` | `256` | Bounds process count (fork bombs, runaway helpers) |
| `restart` | `unless-stopped` | Restarts after a crash or reboot |
| `volumes` | `doctool-data:/data` | Named volume for all state |

## 2. Data volume layout

Everything doctool writes lives under `/data` (the `doctool-data` volume):

```text
/data
├── doctool.sqlite3        # library, versions, tasks
├── blobs/                 # files, addressed by SHA-256
└── office/
    ├── profile/           # persistent, macro-locked LibreOffice profile
    │   ├── user/registrymodifications.xcu
    │   └── .ready         # written after the first successful conversion
    └── job-*/             # one per conversion, deleted when it ends
```

To back up doctool, stop the container and copy the volume. `office/profile` can be deleted
safely; doctool rebuilds it (the next conversion is slower, see
[office-setup.md](office-setup.md#3-the-first-conversion-is-slower)).

## 3. Block outgoing network traffic

doctool strips the external references it knows about from DOCX/XLSX/PPTX and HTML files, but it
does not stop the LibreOffice process from opening network connections. Legacy
(`.doc`/`.xls`/`.ppt`), ODF and RTF files are passed to LibreOffice unchanged, but its profile is
set not to fetch linked content (measured for legacy `.doc` only; see
[office-module.md](office-module.md#honest-limits)). Treat that as the first barrier, not the only
one: give the container no outbound network access as defence in depth.

The repository does not ship an egress rule yet. Two common ways to add one (untested here):

- **Internal network behind the proxy.** Put doctool on a Compose network with `internal: true`
  and remove its `ports` entry. Only the reverse proxy joins both that network and an external
  one, so doctool can answer the proxy but cannot reach the internet.
- **Host firewall.** Drop new outbound connections from the container's address, for example in
  the `DOCKER-USER` iptables chain, and allow only replies.

Check it from inside the container (expect a failure):

```bash
docker compose exec doctool python -c "import urllib.request as u; u.urlopen('https://example.com', timeout=5)"
```

## 4. Expose it beyond localhost

Do these steps in order, and only on a network you trust:

1. Put a reverse proxy (for example Caddy, nginx or Traefik) in front of doctool and turn on
   authentication there. doctool itself has no users or passwords.
2. Serve it over HTTPS from the proxy.
3. Add the public host name to `DOCTOOL_ALLOWED_HOSTS` (comma-separated), or the proxy's requests
   are rejected by the `Host` check.
4. Keep doctool's own port unreachable from the network: leave the `127.0.0.1:` prefix on the
   published port, or use the internal network from [step 3](#3-block-outgoing-network-traffic).

## Verify it worked

```bash
docker compose ps
curl -s http://127.0.0.1:8000/api/v1/health
curl -s http://127.0.0.1:8000/api/v1/tools
```

- `docker compose ps` shows the service as `healthy`.
- The health call returns `{"status":"ok","version":...}`.
- In the tools list, `word2pdf` reports `"available":true`. Then open <http://127.0.0.1:8000>,
  convert a small DOCX with Word to PDF, and download the result.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Office tools greyed out | `soffice` not at `DOCTOOL_SOFFICE` | Check `docker compose exec doctool ls -l /usr/bin/soffice`; rebuild if missing |
| `400 Invalid host header` | `Host` not in `DOCTOOL_ALLOWED_HOSTS` | Add the name the proxy sends |
| First conversion times out | Profile build is slow under the CPU limit | Wait for the start-up warm-up (log line `LibreOffice warm-up skipped` means it failed); raise `DOCTOOL_OFFICE_TIMEOUT_SECONDS` |
| Errors writing files | `/data` not writable | Check the volume is mounted and owned by uid 10001 |
| Container killed under load | Memory limit reached | Large spreadsheets or presentations; raise `mem_limit` carefully |

More LibreOffice problems: [office-setup.md](office-setup.md#troubleshooting).

## Related

- [office-setup.md](office-setup.md): LibreOffice install, settings, troubleshooting.
- [office-module.md](office-module.md): Office tools and their security model.
- [SPEC.md](SPEC.md): security requirements (section 9).
