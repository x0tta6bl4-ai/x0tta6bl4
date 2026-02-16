---
name: x0tta6bl4-core
description: Core knowledge and operational guidelines for the x0tta6bl4 project. Use this skill when managing project tasks, understanding architectural context, addressing technical debt, or planning commercialization strategies. It provides access to project overview, technical debt plans, commercialization roadmaps, and utility scripts for security and development.
---

# x0tta6bl4 Core Project Management

## Overview

This skill provides comprehensive context, strategic plans, and utility scripts for managing and developing the x0tta6bl4 project. It centralizes essential documentation and automates common development and security tasks to ensure adherence to project standards and efficient progress.

## Core Capabilities

This skill encapsulates several key areas of the x0tta6bl4 project:

### 1. Project Context and Architecture
Access to the foundational understanding of the x0tta6bl4 autonomous cyber-physical system, its architecture, and philosophy.
- **Reference**: To understand the project's overall design, components, and current status, see [project_overview.md](references/project_overview.md).

### 2. Technical Debt Management
Detailed plan and roadmap for identifying, prioritizing, and eliminating technical debt.
- **Reference**: For a comprehensive plan on technical debt, including critical issues, architectural defects, and sprint roadmaps, see [technical_debt_plan.md](references/technical_debt_plan.md).
- **Script**: To automatically update critical dependencies and address known vulnerabilities, execute `scripts/update_dependencies.sh`.
- **Script**: To perform various security checks on the codebase and dependencies, execute `scripts/check_security.sh`.
- **Script**: To verify current test coverage against project goals, execute `scripts/check_test_coverage.sh`.

### 3. Commercialization Strategy
Strategic roadmap and insights for the commercial launch and revenue generation for the x0tta6bl4 VPN solution.
- **Reference**: For the commercialization roadmap, key actions, and target metrics, see [commercialization_roadmap.md](references/commercialization_roadmap.md).

## Usage Guidance

When interacting with the x0tta6bl4 project, consider the following:
- **Project Context**: Always refer to `project_overview.md` for a holistic understanding of the system before making significant decisions.
- **Technical Debt**: Prioritize tasks from `technical_debt_plan.md`, especially P0 items, and use the provided scripts for automation.
- **Commercialization**: Align all development efforts with the `commercialization_roadmap.md` to ensure the project's strategic goals are met.
- **Meta-Cognitive Approach**: Adhere to the established Protocol Modes and communication rules as detailed in project documentation (e.g., `МЕТА_КОГНИТИВНЫЙ_ПРОМПТЫ_ОБНОВЛЕНЫ.md`).

## Scripts Overview

- **`scripts/update_dependencies.sh`**: Updates Python package dependencies to address security vulnerabilities and outdated versions.
- **`scripts/check_security.sh`**: Runs `pip-audit`, `bandit`, and `safety check` to identify security issues in dependencies and code.
- **`scripts/check_test_coverage.sh`**: Executes `pytest` with coverage reports to ensure code is adequately tested (target >= 75%).

## References Overview

- **`references/project_overview.md`**: Provides a deep analysis of the x0tta6bl4 project, its architecture, technical stack, and current status.
- **`references/technical_debt_plan.md`**: Outlines a comprehensive plan for identifying, prioritizing, and resolving technical debt.
- **`references/commercialization_roadmap.md`**: Details the strategic plan for commercializing the x0tta6bl4 VPN solution.