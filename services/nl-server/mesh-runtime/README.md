# NL Mesh Runtime Source Candidates

Priority source candidates from NL:

```text
build_runtime_state.py
apply_config_auto.py
full_stealth_config.py
rotation_timer.sh
listener_loss_signal.py
publish_client_profile_hint.py
health_check.sh
```

These explain runtime-state, listener loss signals, profile hints, and mesh
health decisions. They should be reviewed first because they directly affect
how VPN health is interpreted.

Reviewed local source currently promoted here:

```text
build_runtime_state.py
listener_loss_signal.py
publish_client_profile_hint.py
vps_build_runtime_state.py
profile_status_api.py
monitor.py
auto_monitor.py
apply_config_auto.py
full_stealth_config.py
rotation_timer.sh
health_check.sh
```

These files are local source-of-truth candidates only. They are not deployed to
NL while `nl_write_allowed=false`.

`auto_monitor.py` matches the current NL hash, but it creates `/opt` log paths
at import time. Its tests use AST extraction so local validation does not create
or modify runtime directories.

`apply_config_auto.py` also matches the current NL hash. It is class C because
runtime execution writes `/usr/local/x-ui/bin/config.json`; local tests cover
only pure config transformations and do not run save/backup/validation actions.

`full_stealth_config.py` matches the current NL hash. It is class C because
runtime execution writes x-ui config and rotation metadata; local tests do not
run `apply_full_stealth()`.

`rotation_timer.sh` matches the current NL hash. It is class C because runtime
execution runs full stealth config and signals Xray; local tests only check
syntax and static mutation evidence.

`health_check.sh` matches the current NL hash. It is class C because runtime
execution can restart `x-ui`; use `health_check_readonly.sh` for local read-only
diagnostics and keep restart behavior behind explicit approval gates.
