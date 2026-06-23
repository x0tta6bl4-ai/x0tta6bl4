# NL Incident Notes

This directory stores historical incident notes and operator evidence for the
NL VPN environment.

These notes are not current execution instructions. Commands recorded inside a
note describe what was planned or done at that timestamp. They do not authorize
future service stops, disables, masks, kills, restarts, cron edits, or other
production mutations.

Before any new NL production change:

- follow the root `AGENTS.md` NL VPN Safety Guard;
- require an explicit current user request for the exact mutating action;
- write a fresh note with timestamp, command, expected result, and rollback;
- prefer read-only evidence collection when approval is absent.
