# NL server and VPN diagnostics - 2026-06-06

Server: `89.125.1.107` (`01164.com`)
Local host: `/mnt/projects`, `x0ttta6bl4-PC`

## Current status

- Local VPN check: PASS, warnings 0.
- Local exit IP through VPN: `89.125.1.107`.
- Local first-party SOCKS proxy: `127.0.0.1:10818`.
- Local TUN interface: `singbox_tun`, `172.18.0.1/30`.
- NL services active: `x-ui`, `warp-svc`, `ghost-vpn`, `ghost-tcp-bridge`, `nginx`, `fail2ban`.
- NL failed systemd units: none.
- Server resources: CPU/load low, RAM OK, swap unused, root disk about 73% used.

## Main findings

### Critical: x-ui panel is exposed publicly

`x-ui` listens on TCP `628`, and UFW allows `628/tcp` from `Anywhere`.

Impact: the control panel is reachable from the Internet. This is the largest security risk found.

Recommended fix: restrict `628/tcp` to trusted source IPs or put it behind SSH/VPN only.

### High: root cron restarts x-ui every 15 minutes

Root crontab contains:

```cron
*/15 * * * * /usr/bin/python3 /usr/local/bin/proactive_auditor.py
*/15 * * * * /usr/bin/python3 /usr/local/bin/dynamic_egress_optimizer.py
0 3 * * * /usr/bin/python3 /usr/local/bin/rotate_sni.py
```

The repeated `x-ui` restarts at `09:00:01`, `09:15:01`, and `09:30:02 UTC` match these cron jobs.

Primary culprit: `/usr/local/bin/dynamic_egress_optimizer.py`.

Why: it edits `/usr/local/x-ui/bin/config.json` and runs `systemctl restart x-ui` whenever it thinks DNS host choices changed. After restart, `x-ui` regenerates its config from its database, so those direct config edits disappear. On the next cron run the script sees the same "missing" values again and restarts `x-ui` again.

Impact: active VPN sessions are interrupted every 15 minutes.

Recommended fix: disable this cron entry or rewrite the script so it does not edit x-ui generated config directly and does not restart `x-ui` on every run.

### High: previous outage source

Earlier outage was caused by local Codex session:

`/home/x0ttta6bl4/.codex/sessions/2026/06/02/rollout-2026-06-02T20-07-45-019e894e-3932-71f1-9e4d-cc7a76688a26.jsonl`

Evidence around lines `57130`, `57159`, `57170`: it stopped, disabled, masked `x-ui.service`, and symlinked the unit to `/dev/null`.

Current status: `x-ui.service` is restored and active.

### Medium: SSH password auth still enabled

`sshd -T` showed:

- `permitrootlogin without-password`
- `passwordauthentication yes`
- `pubkeyauthentication yes`

`fail2ban` is active and has bans, so bots are probing SSH.

Recommended fix: if no password users are required, set `PasswordAuthentication no`; otherwise restrict SSH by trusted IP or VPN.

### Medium: too many public ports

Public listeners include `22`, `80`, `443`, `628`, `2083`, `39829`, `4434`, `8443`, `18080`, `22080-22083`, `2443`, and `34506`.

This increases attack surface. Some may be intentional, but each should have an owner and purpose.

### Medium: deprecated Shadowsocks inbound

`x-ui` has a Shadowsocks inbound on `34506`. Xray logs warn that Shadowsocks support is deprecated.

Recommended fix: migrate that client path to VLESS/Reality or remove it if unused.

### Medium: stale TCP states after restarts

After the 09:30 restart, sockets on `443/2083` had multiple `CLOSE-WAIT` and `LAST-ACK` states. This is expected after forced service restarts, but repeated restarts can keep creating churn.

### Low/Medium: local proxy environment still polluted in current shell

The current Codex process still had old proxy env values pointing to `7890` and `10918`. New shell config was fixed earlier, and routing through `singbox_tun` works, but long-lived processes may still inherit old proxy variables.

Recommended fix: restart affected shells/apps or unset those variables in the current process when testing.

## Validation commands run

Local:

```bash
bash scripts/vpn_status.sh --check --no-color
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy -u ftp_proxy \
  curl -4 https://www.gstatic.com/generate_204
curl --socks5-hostname 127.0.0.1:10818 https://www.gstatic.com/generate_204
```

Remote:

```bash
systemctl is-active x-ui warp-svc ghost-vpn ghost-tcp-bridge nginx fail2ban
systemctl --failed
crontab -l
journalctl --since "2026-06-06 09:29:50" --until "2026-06-06 09:30:12"
nl -ba /usr/local/bin/dynamic_egress_optimizer.py
nl -ba /usr/local/bin/proactive_auditor.py
ufw status verbose
ss -lntup
```

## Recommended next repair

1. Remove or comment out the `dynamic_egress_optimizer.py` cron line.
2. Keep `proactive_auditor.py` only after reviewing whether it should restart `x-ui` based on local ports.
3. Restrict public access to `628/tcp`.
4. Disable SSH password auth if all admins use keys.
5. Migrate or remove Shadowsocks inbound `34506`.
6. Re-run local `bash scripts/vpn_status.sh --check --no-color` and remote socket checks after one full 15-minute cron interval.

## Remediation applied - 2026-06-06 09:36-09:46 UTC

Backup created on the NL server:

```text
/root/x0tta-vpn-fix-20260606T093559Z
```

Applied changes:

- Commented out the root crontab entry for `/usr/local/bin/dynamic_egress_optimizer.py`.
- Removed public UFW allow rules for `628/tcp`.
- Added explicit UFW deny rules for `628/tcp` on IPv4 and IPv6.

Current root crontab:

```cron
*/15 * * * * /usr/bin/python3 /usr/local/bin/proactive_auditor.py
# disabled 20260606T093638Z: caused repeated x-ui restarts; */15 * * * * /usr/bin/python3 /usr/local/bin/dynamic_egress_optimizer.py
0 3 * * * /usr/bin/python3 /usr/local/bin/rotate_sni.py
```

Post-fix validation:

- Local VPN status: PASS, warnings 0.
- Local VPN exit IP: `89.125.1.107`.
- `443/tcp`: open.
- `2083/tcp`: open.
- `628/tcp`: closed or filtered externally.
- Remote services active: `x-ui`, `warp-svc`, `ghost-vpn`, `ghost-tcp-bridge`, `nginx`, `fail2ban`, `ssh`.
- Remote failed systemd units: none.
- `x-ui` did not restart at the next `09:45 UTC` cron interval. `ActiveEnterTimestamp` remained `Sat 2026-06-06 09:30:02 UTC`, `NRestarts=0`.

Remaining deliberate non-changes:

- SSH password auth was not disabled to avoid locking out any password-only human users without confirmation.
- Shadowsocks inbound `34506` was not removed because it may still serve clients.
- Broad public listener cleanup was not done because each port needs an owner/purpose check before closing.

## Panel access restored - 2026-06-06 09:51 UTC

User requested public panel access to be restored.

Applied changes:

- Removed UFW deny rules for `628/tcp`.
- Added UFW allow rules for `628/tcp` on IPv4 and IPv6.

Post-restore validation:

- `x-ui` service: active.
- `x-ui` listener: `*:628`.
- External TCP check: `628/tcp` open.
- HTTP check for the panel path returned `307`, meaning the x-ui web server is reachable and redirecting normally.
- Local VPN status remained PASS, warnings 0.

## Inbounds page loading fix - 2026-06-06 10:07-10:11 UTC

Problem observed: the x-ui Inbounds page opened but stayed on `Loading...`.

Finding:

- The `inbounds` table had a broken unused row:
  - `id=5`
  - `port=8443`
  - `protocol=vless`
  - several important fields were `NULL`
  - `settings={}` and `stream_settings={}`
- This row had no client traffic rows and was not present in the active Xray listener set.
- Port `8443` is served by `nginx`, not by Xray.

Applied changes:

- Created DB backup:
  - `/root/x0tta-vpn-fix-20260606T093559Z/x-ui.db.before-inbound5-fix.20260606T100757Z`
  - `/root/x0tta-vpn-fix-20260606T093559Z/x-ui.db.before-delete-inbound5.20260606T101001Z`
- Removed the broken unused inbound row `id=5`.
- Restarted `x-ui`.

Post-fix state after deleting broken inbound `id=5`:

- Active inbounds in DB: `39829`, `443`, `2083`, `34506`.
- Active listeners: `628`, `443`, `2083`, `39829`, `34506`, `2096`; `8443` remains `nginx`.
- External checks: `443`, `2083`, `39829`, `628` all open.
- Local VPN status remained PASS, warnings 0.

## Inbounds UI Shadowsocks fix - 2026-06-06 10:21-10:32 UTC

Problem observed after deleting broken inbound `id=5`: browser automation could log in and `/panel/api/inbounds/list` returned HTTP 200 with 4 inbounds, but the Inbounds page still stayed on `Loading...`.

Browser error:

```text
TypeError: Cannot read properties of undefined (reading 'map')
```

Finding:

- The remaining Shadowsocks inbound `id=7` on port `34506` had valid `method`, `password`, and `network` settings.
- Its `settings` JSON did not include a `clients` array.
- The x-ui frontend expects `settings.clients` to exist and calls `.map(...)` on it for Shadowsocks rows.

Applied changes:

- Created DB backup:
  - `/root/x0tta-vpn-fix-20260606T093559Z/x-ui.db.before-ss-clients-array.20260606T102312Z`
- Added an empty JSON array to inbound `id=7`:

```json
"clients": []
```

- Preserved the existing Shadowsocks `method`, `password`, and `network` fields.
- Restarted `x-ui`.

Post-fix validation:

- `x-ui` service: active, `NRestarts=0`, PID `23642`.
- Xray PID: `23650`.
- Active listeners: `628`, `443`, `2083`, `39829`, `34506/tcp`, `34506/udp`, `2096`.
- DB inbounds:
  - `39829` VLESS, `clients` array length `41`
  - `443` VLESS, `clients` array length `130`
  - `2083` VLESS, `clients` array length `85`
  - `34506` Shadowsocks, `clients` array length `0`
- Browser validation with Playwright:
  - login OK
  - final URL: `/LiiqMSLWV8cM2MMlFA/panel/inbounds`
  - `Loading...`: false
  - visible inbound rows: 4
  - `/panel/api/inbounds/list`: HTTP 200, success true, ports `39829`, `443`, `2083`, `34506`
  - page JavaScript errors: none
  - screenshot: `/mnt/projects/xui-inbounds-playwright-recheck.png`
- Temporary test user was deleted and all inbounds were restored to main user `id=1`.
- Local VPN status remained PASS, warnings 0.
