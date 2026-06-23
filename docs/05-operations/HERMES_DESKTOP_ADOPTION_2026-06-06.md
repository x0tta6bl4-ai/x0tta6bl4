# Hermes Desktop Adoption Check - 2026-06-06

## Status

Hermes Desktop / Hermes Agent was reviewed from official public docs. It is not
installed in this workspace environment:

- `command -v hermes` returned no path.
- `~/.hermes` was not present.
- Local `hermes-parser` / `hermes-estree` hits are JavaScript parser packages,
  not Nous Research Hermes Agent.

No installer, desktop binary, gateway, OAuth setup, token write, or server write
was run during this check.

## Official Facts Checked

- Desktop page: https://hermes-agent.nousresearch.com/desktop
  - Shows Hermes Desktop for macOS 12+, Windows 10/11, and Linux install via terminal.
  - Shows `Hermes Agent v0.16.0`.
  - Lists Desktop/agent features: shared memory, skills, scheduling,
    delegation/subagents, web/browser/image/TTS tools, and sandbox backends.
- Docs: https://hermes-agent.nousresearch.com/docs
  - CLI-only install command: `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash`.
  - Windows install command: `iex (irm https://hermes-agent.nousresearch.com/install.ps1)`.
  - `hermes setup --portal` performs OAuth and enables Nous Tool Gateway.
- Installation docs: https://hermes-agent.nousresearch.com/docs/getting-started/installation
  - Installer manages dependencies, clone/venv, global `hermes` launcher, and config.
  - Per-user install writes under `~/.hermes/` and `~/.local/bin/hermes`.
  - Service-user installs are supported; browser dependencies may require a one-time admin command.
- Configuration docs: https://hermes-agent.nousresearch.com/docs/user-guide/configuration/
  - Terminal backends include `local`, `docker`, `ssh`, `modal`, `daytona`, and `singularity`.
  - SSH backend needs `TERMINAL_SSH_HOST` and `TERMINAL_SSH_USER`.
  - Remote file sync stores touched files under `~/.hermes/cache/remote-syncs/<session-id>/`.
- Security docs: https://hermes-agent.nousresearch.com/docs/user-guide/security
  - Default approval mode is manual.
  - `approvals.mode: off`, `--yolo`, or `HERMES_YOLO_MODE=1` bypass approvals and should not be used for production infrastructure.
  - Gateway allowlists are the safe default for bots with terminal access.

## Date Boundary

The official Desktop page does not show a release date in the fetched content.
Third-party search results mention June 2-3, 2026 public preview coverage, but
that is not treated here as authoritative release evidence.

## Recommended Local Path

Use local Desktop only for review and low-risk development tasks first:

```bash
# macOS/Windows: use the official Desktop installer from:
# https://hermes-agent.nousresearch.com/desktop

# Linux/WSL CLI-only path, if explicitly approved:
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
source ~/.bashrc
hermes doctor
hermes setup --portal
```

Do not paste provider tokens, OAuth refresh tokens, SSH private keys, or bot
tokens into chat. Use local terminal prompts only.

## Recommended Remote Gateway Path

Do not install Hermes on production VPN hosts such as NL until it has been
tested on a separate disposable VPS or isolated user.

Safer pilot shape:

1. Create a separate low-cost VPS or a dedicated unprivileged `hermes` user.
2. Install Hermes as that user, not as root.
3. Keep `approvals.mode: manual`.
4. Do not enable `--yolo`, `HERMES_YOLO_MODE=1`, or `approvals.mode: off`.
5. Prefer Docker backend for risky repo work, or SSH backend only to a
   non-production sandbox.
6. Configure messaging/Remote Gateway with explicit allowlists only.
7. Run `hermes doctor` and `hermes portal info` before giving it real work.
8. Run one read-only task first, then one small non-production edit task.

## Production VPN Guardrails

For this workspace, Hermes must not receive broad shell access to NL VPN
infrastructure until these are true:

- It runs under a dedicated unprivileged account.
- It has no passwordless sudo to `systemctl`, firewall, x-ui, xray, nginx, or
  VPN profile distribution commands.
- Gateway access is allowlisted.
- Approval mode is manual.
- A separate rollback note exists for any service write.
- The operator explicitly approves the exact command scope for production work.

## Next Decision

Choose one:

- Desktop-only review on a laptop: low risk, no server access.
- Disposable VPS pilot: best way to test Remote Gateway 24/7 behavior.
- Production integration: not recommended yet.
