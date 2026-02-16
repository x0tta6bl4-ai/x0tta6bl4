Orchestrate the x0tta6bl4 self-healing mesh network using the full MAPE-K cycle.

Read the skill file at `skills/x0tta6bl4-mesh-orchestrator/SKILL.md` and follow the 5-step orchestration cycle (Monitor → Analyze → Plan → Execute → Verify).

Consult these references as needed:
- `skills/x0tta6bl4-mesh-orchestrator/references/api-guide.md` for API patterns
- `skills/x0tta6bl4-mesh-orchestrator/references/pqc-algorithms.md` for PQC details

Available scripts:
- `python3 skills/x0tta6bl4-mesh-orchestrator/scripts/validate-mesh.py --metrics` for telemetry
- `python3 skills/x0tta6bl4-mesh-orchestrator/scripts/validate-mesh.py --verify` for post-heal check
- `python3 skills/x0tta6bl4-mesh-orchestrator/scripts/dao-vote.py --status` for governance status

K8s template: `skills/x0tta6bl4-mesh-orchestrator/assets/mesh-deployment.yaml`

Action or context: $ARGUMENTS
