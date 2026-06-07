# NL Systemd Notes

This directory is for sanitized unit documentation and future reviewed unit
templates only.

Current production truth is collected in:

```text
nl-diagnostics/nl-server-profile/latest/systemd/
```

Do not place production environment values, credentials, or `LoadCredential`
targets here.

Prepared local-only templates:

```text
ghost-access-client-compatibility-summary.service
ghost-access-client-compatibility-summary.timer
```

These refresh `/var/lib/ghost-access/client-compatibility/latest.json` from a
local matrix at `/var/lib/ghost-access/client-compatibility/matrix.json` so the
profile status API can serve `/client-compatibility`. They do not restart x-ui,
nginx, Telegram bot, XHTTP/WS services, or any VPN dataplane service.

They are not installed or enabled by this repository. Treat them as reviewed
deployment templates until an explicit operator rollout installs them on NL.
