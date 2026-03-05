#!/usr/bin/env bash
# measure_mttr.sh — MTTR (Mean Time To Recovery) tracker for x0tta6bl4
#
# Usage:
#   # Record incident start (returns INCIDENT_ID):
#   ./measure_mttr.sh start "DB connection pool exhausted"
#
#   # Record recovery:
#   ./measure_mttr.sh resolve INCIDENT_ID
#
#   # View stats (all incidents, running MTTR):
#   ./measure_mttr.sh stats
#
#   # Export CSV for reporting:
#   ./measure_mttr.sh export > mttr_report.csv
#
# SLO target: MTTR < 30 minutes (1800 seconds)
# Data store: ~/.x0tta6bl4/incidents.jsonl  (append-only, one JSON per line)
#
# Dependencies: bash, date, jq (optional — degrades gracefully without it)

set -euo pipefail

INCIDENTS_DIR="${INCIDENTS_DIR:-${HOME}/.x0tta6bl4}"
INCIDENTS_FILE="${INCIDENTS_DIR}/incidents.jsonl"
SLO_SECONDS=1800   # 30 minutes

_ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
_epoch() { date -u +%s; }
_jq_available() { command -v jq &>/dev/null; }

_ensure_dir() {
    mkdir -p "${INCIDENTS_DIR}"
    touch "${INCIDENTS_FILE}"
}

_incident_id() {
    # Short deterministic ID: YYMMDDHHmmss + 4 random hex chars
    printf "INC-%s-%04x" "$(date -u +%Y%m%d%H%M%S)" "$((RANDOM % 65536))"
}

# ---------------------------------------------------------------------------
# start — open a new incident
# ---------------------------------------------------------------------------
cmd_start() {
    local description="${1:-unspecified}"
    _ensure_dir

    local id
    id=$(_incident_id)
    local epoch
    epoch=$(_epoch)
    local ts
    ts=$(_ts)

    local record
    printf -v record '{"id":"%s","description":"%s","started_at":"%s","started_epoch":%d,"resolved_at":null,"resolved_epoch":null,"duration_seconds":null,"within_slo":null}' \
        "${id}" "${description//\"/\\\"}" "${ts}" "${epoch}"

    echo "${record}" >> "${INCIDENTS_FILE}"

    echo "[MTTR] Incident opened: ${id}"
    echo "[MTTR] Description    : ${description}"
    echo "[MTTR] Started at     : ${ts}"
    echo "[MTTR] To resolve run : $0 resolve ${id}"
    echo ""
    echo "${id}"
}

# ---------------------------------------------------------------------------
# resolve — close an existing incident
# ---------------------------------------------------------------------------
cmd_resolve() {
    local id="${1:-}"
    [[ -z "${id}" ]] && { echo "Usage: $0 resolve INCIDENT_ID" >&2; exit 1; }
    _ensure_dir

    local resolve_epoch
    resolve_epoch=$(_epoch)
    local resolve_ts
    resolve_ts=$(_ts)

    # Find the incident line
    local found=0
    local tmp
    tmp=$(mktemp)

    while IFS= read -r line; do
        local line_id
        line_id=$(echo "${line}" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        if [[ "${line_id}" == "${id}" ]]; then
            found=1
            local started_epoch
            started_epoch=$(echo "${line}" | grep -o '"started_epoch":[0-9]*' | cut -d: -f2)
            local duration=$(( resolve_epoch - started_epoch ))
            local within_slo="true"
            [[ ${duration} -gt ${SLO_SECONDS} ]] && within_slo="false"

            # Rewrite the record with resolution data
            local resolved_line
            resolved_line=$(echo "${line}" \
                | sed "s|\"resolved_at\":null|\"resolved_at\":\"${resolve_ts}\"|" \
                | sed "s|\"resolved_epoch\":null|\"resolved_epoch\":${resolve_epoch}|" \
                | sed "s|\"duration_seconds\":null|\"duration_seconds\":${duration}|" \
                | sed "s|\"within_slo\":null|\"within_slo\":${within_slo}|")
            echo "${resolved_line}" >> "${tmp}"

            local mins=$(( duration / 60 ))
            local secs=$(( duration % 60 ))
            echo "[MTTR] Incident resolved : ${id}"
            echo "[MTTR] Resolved at       : ${resolve_ts}"
            echo "[MTTR] Duration          : ${mins}m ${secs}s (${duration}s)"
            if [[ "${within_slo}" == "true" ]]; then
                echo "[MTTR] SLO               : PASS (< 30 min)"
            else
                echo "[MTTR] SLO               : BREACH (> 30 min — ${mins}m ${secs}s)"
            fi
        else
            echo "${line}" >> "${tmp}"
        fi
    done < "${INCIDENTS_FILE}"

    if [[ ${found} -eq 0 ]]; then
        rm -f "${tmp}"
        echo "[MTTR] ERROR: Incident '${id}' not found" >&2
        exit 1
    fi

    mv "${tmp}" "${INCIDENTS_FILE}"
}

# ---------------------------------------------------------------------------
# stats — compute running MTTR from all resolved incidents
# ---------------------------------------------------------------------------
cmd_stats() {
    _ensure_dir

    local total=0
    local resolved=0
    local sum_duration=0
    local breaches=0
    local open=0

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        total=$(( total + 1 ))

        local dur
        dur=$(echo "${line}" | grep -o '"duration_seconds":[0-9]*' | cut -d: -f2)

        if [[ -z "${dur}" || "${dur}" == "null" ]]; then
            open=$(( open + 1 ))
        else
            resolved=$(( resolved + 1 ))
            sum_duration=$(( sum_duration + dur ))
            [[ ${dur} -gt ${SLO_SECONDS} ]] && breaches=$(( breaches + 1 ))
        fi
    done < "${INCIDENTS_FILE}"

    echo "=============================="
    echo " MTTR Report — x0tta6bl4"
    echo "=============================="
    echo " Total incidents  : ${total}"
    echo " Resolved         : ${resolved}"
    echo " Open (active)    : ${open}"
    echo " SLO breaches     : ${breaches}"

    if [[ ${resolved} -gt 0 ]]; then
        local mttr=$(( sum_duration / resolved ))
        local mttr_min=$(( mttr / 60 ))
        local mttr_sec=$(( mttr % 60 ))
        local slo_pct=$(( (resolved - breaches) * 100 / resolved ))
        echo " Mean MTTR        : ${mttr_min}m ${mttr_sec}s (${mttr}s)"
        echo " SLO compliance   : ${slo_pct}% (target: within 30 min)"
        echo "------------------------------"
        if [[ ${mttr} -le ${SLO_SECONDS} ]]; then
            echo " STATUS: SLO MET (MTTR ${mttr_min}m ${mttr_sec}s < 30 min)"
        else
            echo " STATUS: SLO BREACH — MTTR ${mttr_min}m ${mttr_sec}s > 30 min"
            echo " ACTION: Review incidents for systemic patterns"
        fi
    else
        echo " Mean MTTR        : N/A (no resolved incidents)"
    fi
    echo "=============================="
}

# ---------------------------------------------------------------------------
# list — show all incidents in human-readable form
# ---------------------------------------------------------------------------
cmd_list() {
    _ensure_dir
    local filter="${1:-all}"   # all | open | resolved | breach

    echo "ID                        | Started             | Duration | SLO    | Description"
    echo "--------------------------|---------------------|----------|--------|------------------"

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue

        local id started dur within_slo description
        id=$(echo "${line}" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        started=$(echo "${line}" | grep -o '"started_at":"[^"]*"' | cut -d'"' -f4)
        dur=$(echo "${line}" | grep -o '"duration_seconds":[0-9]*' | cut -d: -f2)
        within_slo=$(echo "${line}" | grep -o '"within_slo":[a-z]*' | cut -d: -f2)
        description=$(echo "${line}" | grep -o '"description":"[^"]*"' | cut -d'"' -f4 | cut -c1-40)

        local dur_str="open"
        local slo_str="--"
        if [[ -n "${dur}" && "${dur}" != "null" ]]; then
            local m=$(( dur / 60 ))
            local s=$(( dur % 60 ))
            dur_str="${m}m${s}s"
            slo_str="${within_slo}"
        fi

        case "${filter}" in
            open)     [[ "${dur_str}" != "open" ]] && continue ;;
            resolved) [[ "${dur_str}" == "open" ]] && continue ;;
            breach)   [[ "${within_slo}" != "false" ]] && continue ;;
        esac

        printf "%-26s| %-20s| %-9s| %-7s| %s\n" \
            "${id}" "${started}" "${dur_str}" "${slo_str}" "${description}"
    done < "${INCIDENTS_FILE}"
}

# ---------------------------------------------------------------------------
# export — CSV for Grafana / external reporting
# ---------------------------------------------------------------------------
cmd_export() {
    _ensure_dir
    echo "id,description,started_at,resolved_at,duration_seconds,within_slo"

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        local id description started resolved dur within_slo
        id=$(echo "${line}" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        description=$(echo "${line}" | grep -o '"description":"[^"]*"' | cut -d'"' -f4)
        started=$(echo "${line}" | grep -o '"started_at":"[^"]*"' | cut -d'"' -f4)
        resolved=$(echo "${line}" | grep -o '"resolved_at":"[^"]*"' | cut -d'"' -f4 | sed 's/null//')
        dur=$(echo "${line}" | grep -o '"duration_seconds":[^,}]*' | cut -d: -f2 | sed 's/null//')
        within_slo=$(echo "${line}" | grep -o '"within_slo":[^,}]*' | cut -d: -f2 | sed 's/null//')
        printf '"%s","%s","%s","%s",%s,%s\n' \
            "${id}" "${description}" "${started}" "${resolved}" \
            "${dur:-}" "${within_slo:-}"
    done < "${INCIDENTS_FILE}"
}

# ---------------------------------------------------------------------------
# check-slo — exit 1 if running MTTR violates SLO (for CI gates)
# ---------------------------------------------------------------------------
cmd_check_slo() {
    _ensure_dir
    local resolved=0
    local sum_duration=0

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        local dur
        dur=$(echo "${line}" | grep -o '"duration_seconds":[0-9]*' | cut -d: -f2)
        if [[ -n "${dur}" && "${dur}" != "null" ]]; then
            resolved=$(( resolved + 1 ))
            sum_duration=$(( sum_duration + dur ))
        fi
    done < "${INCIDENTS_FILE}"

    if [[ ${resolved} -eq 0 ]]; then
        echo "[MTTR] No resolved incidents — SLO check skipped"
        exit 0
    fi

    local mttr=$(( sum_duration / resolved ))
    local mttr_min=$(( mttr / 60 ))

    if [[ ${mttr} -le ${SLO_SECONDS} ]]; then
        echo "[MTTR] SLO OK — MTTR=${mttr_min}m (< 30 min)"
        exit 0
    else
        echo "[MTTR] SLO BREACH — MTTR=${mttr_min}m (> 30 min)" >&2
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# purge — remove resolved incidents older than N days (default: 90)
# ---------------------------------------------------------------------------
cmd_purge() {
    local days="${1:-90}"
    local cutoff=$(( $(_epoch) - days * 86400 ))
    _ensure_dir

    local tmp
    tmp=$(mktemp)
    local removed=0

    while IFS= read -r line; do
        [[ -z "${line}" ]] && continue
        local resolved_epoch
        resolved_epoch=$(echo "${line}" | grep -o '"resolved_epoch":[0-9]*' | cut -d: -f2)
        if [[ -n "${resolved_epoch}" && "${resolved_epoch}" != "null" && "${resolved_epoch}" -lt "${cutoff}" ]]; then
            removed=$(( removed + 1 ))
        else
            echo "${line}" >> "${tmp}"
        fi
    done < "${INCIDENTS_FILE}"

    mv "${tmp}" "${INCIDENTS_FILE}"
    echo "[MTTR] Purged ${removed} incidents older than ${days} days"
}

# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------
CMD="${1:-help}"
shift || true

case "${CMD}" in
    start)   cmd_start "$@" ;;
    resolve) cmd_resolve "$@" ;;
    stats)   cmd_stats "$@" ;;
    list)    cmd_list "$@" ;;
    export)  cmd_export "$@" ;;
    check-slo) cmd_check_slo "$@" ;;
    purge)   cmd_purge "$@" ;;
    help|--help|-h)
        echo "Usage: $0 {start|resolve|stats|list|export|check-slo|purge}"
        echo ""
        echo "  start   'description'     Open a new incident"
        echo "  resolve INCIDENT_ID       Mark incident as resolved"
        echo "  stats                     Show MTTR summary"
        echo "  list    [all|open|resolved|breach]  List incidents"
        echo "  export                    CSV dump for reporting"
        echo "  check-slo                 Exit 1 if MTTR > 30 min (CI gate)"
        echo "  purge   [days=90]         Remove old resolved incidents"
        echo ""
        echo "  Data file: ${INCIDENTS_FILE}"
        echo "  SLO target: < ${SLO_SECONDS}s (30 min)"
        ;;
    *)
        echo "Unknown command: ${CMD}" >&2
        echo "Run '$0 help' for usage" >&2
        exit 1
        ;;
esac
