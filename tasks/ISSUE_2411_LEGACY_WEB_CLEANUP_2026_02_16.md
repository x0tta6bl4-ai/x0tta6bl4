# Issue #2411: Legacy Web Cleanup (MD5 -> bcrypt) - Target Sprint 2026-02-16

**Status:** Planned

## Context
Legacy PHP stack under `/web/**` contains weak password hashing and legacy crypto patterns. This stack is **out of scope** for the current API hardening sprint and is quarantined per security boundary.

## Impact
- Weak password hashing (MD5) in legacy PHP flows.
- No CI/CD coverage for legacy web.
- Risk of credential compromise if exposed publicly.

## Scope (Files/Areas)
- `web/html/index.php` (`GenPass` uses MD5)
- `web/html/form/account.php` (uses `GenPass`)
- `web/dvijok/index.php` (MD5-based password generator)
- `web/dvijok/form/account.php` (MD5-based function)
- `web/login/` (mailer uses MD5 for boundary/cid; not password but can be reviewed)

## Desired Fixes
1. Replace MD5-based password hashing with bcrypt (PHP `password_hash()` + `password_verify()`).
2. Add migration path for existing hashes (rehash on login).
3. Add CSRF tokens on forms (if missing).
4. Add rate limiting on login endpoints.
5. Ensure secrets are loaded from environment and not hard-coded.

## Security Boundary (Current)
- Legacy web is quarantined and **not** exposed in production.
- No user secrets/tokens should flow through `/web/**`.

## Acceptance Criteria
- No MD5 used for password hashing in legacy PHP auth flows.
- All login/registration/reset flows use bcrypt.
- CSRF protection enabled on auth-related forms.
- Rate limiting configured for login attempts.
- Legacy web stack remains quarantined until fixes validated.

## Notes
- Coordinate with `.x0tta6bl4/security-audit-2026-01-26.md` for boundary tracking.
