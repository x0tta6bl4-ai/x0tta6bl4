# Packet 09: Network Runtime Review

## Objective

Review the `network_runtime` package and verify the network/eBPF/runtime
evidence contracts before they leave the dirty worktree.

## Scope

- `src/network/**`
- `src/libx0t/network/**`
- Network and eBPF unit tests listed by the dirty-worktree package.
- The final committed package excludes remaining Ghost Pulse delivery files
  that are still tracked by the refreshed dirty-worktree review separately.

## Result

Completed with segmented verification. The package changes are present in
`HEAD` at `086be00cb feat(network): add runtime evidence contracts`, with
follow-up exporter evidence at
`7388bfa61 chore(network): update ebpf exporter evidence`. `network_runtime`
no longer appears as a dirty package in the refreshed review.

## Verification

- `python3 -m py_compile` over reviewed network/eBPF Python paths: passed.
- `git diff --check`: passed.
- `PYTHONPATH=. python3` import-order smoke for `src.network.ebpf.bcc_probes`
  then `src.libx0t.network.ebpf.bcc_probes`: passed.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/network/ebpf/test_ebpf_loader_module_unit.py tests/unit/network/ebpf/test_libx0t_ebpf_runtime_thinking_unit.py -q --no-cov`:
  `16 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/network/ebpf/test_bcc_probes_unit.py tests/unit/network/ebpf/test_bcc_probes_observed_state_unit.py tests/unit/network/ebpf/test_libx0t_ebpf_runtime_thinking_unit.py -q --no-cov`:
  `11 passed`.
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/network/ebpf/test_pqc_xdp_loader_observed_state_unit.py -q --no-cov`:
  `5 passed`.
- eBPF tail from `test_pqc_xdp_loader_observed_state_unit.py` onward:
  `273 passed`.
- Remaining network directories plus `tests/unit/libx0t/network`:
  `655 passed`.
- Full ordered network run reached `2953 passed, 3 skipped` before stopping on
  stale in-process `random` state while the package was being committed in
  parallel. Current `HEAD` includes `import random` in
  `src/network/resilience/make_never_break.py`; current-head follow-up
  `PYTHONPATH=. ./.venv/bin/pytest tests/unit/network/test_resilience.py -q --no-cov`
  returned `26 passed`.
- Current-head tail from `tests/unit/network/test_resilience.py` through the
  remaining top-level network files plus `tests/unit/libx0t/network` returned
  `276 passed`.

## Residual Risk

A single fresh end-to-end ordered run was not repeated after the parallel
commit because the prior ordered run took over an hour. The current-head
focused and tail checks cover the failure point and remaining tests.
