# NL Ghost Access Source Candidates

Priority source candidates from NL:

```text
run_vpn_delivery_canary.py
run_vpn_service_access_agent.py
sync_spb_standalone_clients.py
sync_xray_device_activity.py
xray_runtime_user_manager.py
xui_client_manager.py
```

These scripts connect Ghost Access, canary checks, x-ui runtime user state, and
subscription/access health.

Some older local backup copies exist, but gap-analysis shows their hashes mostly
differ from current NL. Treat backups as history, not source of truth.

Reviewed source now copied here:

```text
check_bot_user_chains.py
run_vpn_delivery_canary.py
run_vpn_service_access_agent.py
sync_spb_standalone_clients.py
sync_xray_device_activity.py
xray_runtime_user_manager.py
xui_client_manager.py
```

`sync_xray_device_activity.py` matches the current NL source hash and has local
tests for access-log parsing, x-ui helper parsing, state cursor behavior and
missing-log handling. It is still not deployable to NL while NL is read-only.

The canary, service-access agent, runtime user manager, and x-ui client manager
also match current NL hashes. They are class C review-only sources because they
can read production databases, alter runtime Xray users, or modify x-ui client
state. Do not run them locally or deploy them to NL without an explicit mutation
gate.

`sync_spb_standalone_clients.py` also matches the current NL source hash, but SPB
is currently disabled and not used. Treat this as inactive class C review-only
source: at runtime it reads active UUIDs from NL, writes a remote SPB Xray
config, and restarts remote `xray`. Keep it non-deployable and do not use it for
VPN recovery while SPB remains offline.
