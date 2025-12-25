# Windsurf Integration Overview

Status: Draft

This folder contains project rules, workflows, and usage guidance for using Windsurf effectively with x0tta6bl4.

Contents:
- project-structure.md — Always-on rules for repository hygiene and layout.
- cleanup-workflow.yaml — Guided cleanup/scanning workflow (non-destructive by default).
- usage-guide.md — How to use Windsurf with this repo, common commands and flows.

Conventions:
- All destructive actions are disabled by default. Review steps first.
- Use dry-run flags wherever possible. Promote to active only after review.
- Prefer DVC/MinIO for datasets and large artifacts.

Related docs:
- README.MIGRATION.md — end-to-end migration plan
- .gitlab-ci.yml — CI jobs to enforce hygiene
