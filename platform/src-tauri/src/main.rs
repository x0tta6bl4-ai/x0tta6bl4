#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::BTreeMap;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

const RUNTIME_STATE_PATH: &str = "/opt/x0tta6bl4-mesh/state/runtime-state.json";
const CLIENT_PROFILE_HINT_PATH: &str = "/opt/x0tta6bl4-mesh/state/client-profile-hint.json";
const LISTENER_SIGNAL_PATH: &str = "/opt/x0tta6bl4-mesh/state/listener-loss-signal.json";
const PROJECT_ROOT_ENV: &str = "X0TTA6BL4_PROJECT_ROOT";
const INSTALLED_PROJECT_ROOT: &str = "/opt/x0tta6bl4";
const DEV_PROJECT_ROOT: &str = "/mnt/projects";
const CORE_API_PORT: u16 = 8000;
const CORE_API_PID_PATH: &str = "/tmp/x0tta6bl4-core-api.pid";
const CORE_API_LOG_PATH: &str = "/tmp/x0tta6bl4-core-api.log";
const DEFAULT_CORE_API_APP_MODULE: &str = "src.core.app_desktop:app";
const PACKAGED_DESKTOP_CORE_API_PATH: &str = "/usr/lib/x0tta6bl4/desktop_core_api.py";
const CORE_API_SYSTEMD_UNIT: &str = "x0tta6bl4-core-api.service";
const FULL_CORE_API_PORT: u16 = 8001;
const FULL_CORE_API_PID_PATH: &str = "/tmp/x0tta6bl4-full-core-api.pid";
const FULL_CORE_API_LOG_PATH: &str = "/tmp/x0tta6bl4-full-core-api.log";
const DEFAULT_FULL_CORE_API_APP_MODULE: &str = "src.core.app:app";
const FULL_CORE_API_SYSTEMD_UNIT: &str = "x0tta6bl4-full-core-api.service";
const CORE_API_ALLOWED_PATH_PREFIXES: &[&str] = &[
    "/health", "/status", "/metrics", "/mesh/", "/api/v1/", "/api/v3/",
];
const MESH_SYSTEMD_UNITS: &[&str] = &["x0tta6bl4-node.service", "x0t-agent.service"];

#[derive(Debug, Serialize)]
struct MeshRuntimeStatus {
    active: bool,
    ok: bool,
    service_detected: bool,
    runtime_mode: Option<String>,
    recommended_action: Option<String>,
    recommended_profile: Option<String>,
    best_path: Option<String>,
    best_path_port: Option<u64>,
    transport_health_status: Option<String>,
    subscription_health_status: Option<String>,
    listener_signal_status: Option<String>,
    primary_path_latency_s: Option<f64>,
    secondary_path_latency_s: Option<f64>,
    fallback_nl_path_latency_s: Option<f64>,
    error: Option<String>,
    logs: Vec<String>,
}

#[derive(Debug, Serialize)]
struct MeshToggleResult {
    success: bool,
    active: bool,
    message: String,
    status: MeshRuntimeStatus,
}

#[derive(Debug, Serialize)]
struct MeshMetricsSummary {
    ok: bool,
    mesh_health_score: Option<f64>,
    cpu_usage_percent: Option<f64>,
    memory_usage_bytes: Option<f64>,
    xray_process_running: Option<bool>,
    warp_proxy_running: Option<bool>,
    ghost_fallback_ready: Option<bool>,
    listener_loss_detector_confidence: Option<f64>,
    public_listeners_up: Option<u64>,
    public_listeners_total: Option<u64>,
    vpn_proxy_healthy: Option<bool>,
    vpn_proxy_latency_ms: Option<f64>,
    vpn_established_connections: Option<f64>,
    vpn_packet_loss_percent: Option<f64>,
    vpn_checks_total: Option<f64>,
    vpn_heal_total: Option<f64>,
    raw_metric_count: usize,
    errors: Vec<String>,
}

#[derive(Debug, Serialize)]
struct BackendCapability {
    id: String,
    label: String,
    status: String,
    detail: String,
    entrypoints: Vec<String>,
}

#[derive(Debug, Serialize)]
struct ReadinessSnapshot {
    ok: bool,
    ready: Option<bool>,
    decision: Option<String>,
    passed: Option<u64>,
    failures: Option<u64>,
    warnings: Option<u64>,
    blocker_ids: Vec<String>,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct CoreApiStatus {
    running: bool,
    base_url: String,
    health_ok: bool,
    status_ok: bool,
    pid: Option<u32>,
    log_path: String,
    message: String,
    error: Option<String>,
}

#[derive(Debug, Serialize)]
struct CoreApiEndpointProbe {
    label: String,
    path: String,
    ok: bool,
    status: Option<String>,
    detail: String,
    error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct CoreApiAuthHeaders {
    api_key: Option<String>,
    bearer_token: Option<String>,
    idempotency_key: Option<String>,
    agent_token: Option<String>,
}

fn read_json(path: &str) -> Option<Value> {
    let body = fs::read_to_string(path).ok()?;
    serde_json::from_str(&body).ok()
}

fn string_at(value: Option<&Value>, key: &str) -> Option<String> {
    value
        .and_then(|item| item.get(key))
        .and_then(Value::as_str)
        .map(str::to_owned)
}

fn u64_at(value: Option<&Value>, key: &str) -> Option<u64> {
    value.and_then(|item| item.get(key)).and_then(Value::as_u64)
}

fn f64_at(value: Option<&Value>, key: &str) -> Option<f64> {
    value.and_then(|item| item.get(key)).and_then(Value::as_f64)
}

fn bool_from_metric(value: Option<f64>) -> Option<bool> {
    value.map(|item| item > 0.0)
}

fn looks_like_project_root(path: &Path) -> bool {
    path.join("src/core/app.py").is_file() || path.join("src/core/app_desktop.py").is_file()
}

fn project_root() -> PathBuf {
    if let Ok(raw) = std::env::var(PROJECT_ROOT_ENV) {
        let trimmed = raw.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }

    for candidate in [INSTALLED_PROJECT_ROOT, DEV_PROJECT_ROOT] {
        let path = PathBuf::from(candidate);
        if looks_like_project_root(&path) {
            return path;
        }
    }

    std::env::current_dir().unwrap_or_else(|_| PathBuf::from(DEV_PROJECT_ROOT))
}

fn project_root_display() -> String {
    project_root().to_string_lossy().to_string()
}

fn http_get_local(port: u16, path: &str) -> Result<String, String> {
    http_get_local_with_headers(port, path, "")
}

fn http_get_local_with_headers(
    port: u16,
    path: &str,
    extra_headers: &str,
) -> Result<String, String> {
    let address = format!("127.0.0.1:{port}");
    let socket_address = address
        .to_socket_addrs()
        .map_err(|error| format!("{address}: {error}"))?
        .next()
        .ok_or_else(|| format!("{address}: no socket address"))?;

    let mut stream = TcpStream::connect_timeout(&socket_address, Duration::from_millis(1200))
        .map_err(|error| format!("{address}: {error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_millis(1800)))
        .map_err(|error| format!("{address}: {error}"))?;
    stream
        .set_write_timeout(Some(Duration::from_millis(1200)))
        .map_err(|error| format!("{address}: {error}"))?;

    let request = format!(
        "GET {path} HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\n{extra_headers}\r\n"
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("{address}: {error}"))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| format!("{address}: {error}"))?;

    let mut parts = response.splitn(2, "\r\n\r\n");
    let headers = parts.next().unwrap_or_default();
    let body = parts.next().unwrap_or_default();
    let status_line = headers.lines().next().unwrap_or_default();
    if !status_line.contains(" 200 ") {
        return Err(format!("{address}{path}: {status_line}"));
    }
    Ok(body.to_string())
}

fn http_post_local(port: u16, path: &str, payload: &Value) -> Result<String, String> {
    http_post_local_with_headers(port, path, payload, "")
}

fn http_post_local_with_headers(
    port: u16,
    path: &str,
    payload: &Value,
    extra_headers: &str,
) -> Result<String, String> {
    let address = format!("127.0.0.1:{port}");
    let socket_address = address
        .to_socket_addrs()
        .map_err(|error| format!("{address}: {error}"))?
        .next()
        .ok_or_else(|| format!("{address}: no socket address"))?;

    let mut stream = TcpStream::connect_timeout(&socket_address, Duration::from_millis(1200))
        .map_err(|error| format!("{address}: {error}"))?;
    stream
        .set_read_timeout(Some(Duration::from_millis(2200)))
        .map_err(|error| format!("{address}: {error}"))?;
    stream
        .set_write_timeout(Some(Duration::from_millis(1200)))
        .map_err(|error| format!("{address}: {error}"))?;

    let body = serde_json::to_string(payload).map_err(|error| error.to_string())?;
    let request = format!(
        "POST {path} HTTP/1.0\r\nHost: 127.0.0.1\r\nConnection: close\r\nContent-Type: application/json\r\nContent-Length: {}\r\n{extra_headers}\r\n{}",
        body.as_bytes().len(),
        body
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| format!("{address}: {error}"))?;

    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| format!("{address}: {error}"))?;

    let mut parts = response.splitn(2, "\r\n\r\n");
    let headers = parts.next().unwrap_or_default();
    let body = parts.next().unwrap_or_default();
    let status_line = headers.lines().next().unwrap_or_default();
    if !(status_line.contains(" 200 ")
        || status_line.contains(" 201 ")
        || status_line.contains(" 202 "))
    {
        return Err(format!("{address}{path}: {status_line} {body}"));
    }
    Ok(body.to_string())
}

fn clean_header_value(value: Option<String>, label: &str) -> Result<Option<String>, String> {
    let Some(raw) = value else {
        return Ok(None);
    };
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }
    if trimmed.contains('\n') || trimmed.contains('\r') {
        return Err(format!("{label} contains an invalid newline."));
    }
    Ok(Some(trimmed.to_string()))
}

fn auth_header_lines(auth: Option<CoreApiAuthHeaders>) -> Result<String, String> {
    let Some(auth) = auth else {
        return Ok(String::new());
    };
    let api_key = clean_header_value(auth.api_key, "X-API-Key")?;
    let bearer = clean_header_value(auth.bearer_token, "Bearer token")?;
    let idempotency_key = clean_header_value(auth.idempotency_key, "Idempotency-Key")?;
    let agent_token = clean_header_value(auth.agent_token, "X-Agent-Token")?;
    let mut lines = String::new();
    if let Some(value) = api_key {
        lines.push_str(&format!("X-API-Key: {value}\r\n"));
    }
    if let Some(value) = bearer {
        lines.push_str(&format!("Authorization: Bearer {value}\r\n"));
    }
    if let Some(value) = idempotency_key {
        lines.push_str(&format!("Idempotency-Key: {value}\r\n"));
    }
    if let Some(value) = agent_token {
        lines.push_str(&format!("X-Agent-Token: {value}\r\n"));
    }
    Ok(lines)
}

fn validate_core_api_path(path: &str) -> Result<(), String> {
    if !path.starts_with('/') {
        return Err("Core API path must start with '/'.".to_string());
    }
    if path.contains("://")
        || path.contains('\n')
        || path.contains('\r')
        || path.chars().any(char::is_whitespace)
    {
        return Err("Core API path must be a local path, not a URL.".to_string());
    }
    let allowed = CORE_API_ALLOWED_PATH_PREFIXES.iter().any(|prefix| {
        if prefix.ends_with('/') {
            path.starts_with(prefix)
        } else {
            path == *prefix || path.starts_with(&format!("{prefix}/"))
        }
    });
    if !allowed {
        return Err(format!("Core API path is not allowed: {path}"));
    }
    Ok(())
}

fn parse_prometheus_metrics(body: &str) -> BTreeMap<String, f64> {
    let mut metrics = BTreeMap::new();
    for raw_line in body.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let mut parts = line.split_whitespace();
        let Some(name) = parts.next() else {
            continue;
        };
        let Some(value) = parts.next() else {
            continue;
        };
        if let Ok(parsed) = value.parse::<f64>() {
            metrics.insert(name.to_string(), parsed);
        }
    }
    metrics
}

fn count_metric_prefix(metrics: &BTreeMap<String, f64>, prefix: &str) -> (u64, u64) {
    let mut up = 0;
    let mut total = 0;
    for (name, value) in metrics {
        if name == prefix || name.starts_with(&format!("{prefix}{{")) {
            total += 1;
            if *value > 0.0 {
                up += 1;
            }
        }
    }
    (up, total)
}

fn collect_mesh_metrics() -> MeshMetricsSummary {
    let mut metrics = BTreeMap::new();
    let mut errors = Vec::new();

    for (port, path) in [(9090_u16, "/"), (9091_u16, "/")] {
        match http_get_local(port, path) {
            Ok(body) => metrics.extend(parse_prometheus_metrics(&body)),
            Err(error) => errors.push(error),
        }
    }

    let (public_listeners_up, public_listeners_total) =
        count_metric_prefix(&metrics, "xray_public_listener_status");

    MeshMetricsSummary {
        ok: !metrics.is_empty() && errors.len() < 2,
        mesh_health_score: metrics.get("mesh_health_score").copied(),
        cpu_usage_percent: metrics.get("mesh_cpu_usage_percent").copied(),
        memory_usage_bytes: metrics.get("mesh_memory_usage_bytes").copied(),
        xray_process_running: bool_from_metric(metrics.get("xray_process_running").copied()),
        warp_proxy_running: bool_from_metric(metrics.get("warp_proxy_running").copied()),
        ghost_fallback_ready: bool_from_metric(metrics.get("ghost_fallback_ready").copied()),
        listener_loss_detector_confidence: metrics
            .get("listener_loss_detector_confidence")
            .copied(),
        public_listeners_up: (public_listeners_total > 0).then_some(public_listeners_up),
        public_listeners_total: (public_listeners_total > 0).then_some(public_listeners_total),
        vpn_proxy_healthy: bool_from_metric(metrics.get("vpn_proxy_healthy").copied()),
        vpn_proxy_latency_ms: metrics.get("vpn_proxy_latency_ms").copied(),
        vpn_established_connections: metrics.get("vpn_established_connections").copied(),
        vpn_packet_loss_percent: metrics.get("vpn_packet_loss_percent").copied(),
        vpn_checks_total: metrics.get("vpn_checks_total").copied(),
        vpn_heal_total: metrics.get("vpn_heal_total").copied(),
        raw_metric_count: metrics.len(),
        errors,
    }
}

fn systemctl(args: &[&str]) -> Result<String, String> {
    let output = Command::new("systemctl")
        .arg("--no-ask-password")
        .args(args)
        .output()
        .map_err(|error| {
            if error.kind() == std::io::ErrorKind::NotFound {
                "systemctl is not available on this host. Local mesh service control is supported on Linux/systemd only.".to_string()
            } else {
                error.to_string()
            }
        })?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    if output.status.success() {
        return Ok(stdout);
    }

    let detail = if stderr.is_empty() {
        stdout
    } else if stdout.is_empty() {
        stderr
    } else {
        format!("{stderr}; {stdout}")
    };
    Err(format!(
        "systemctl {} failed: {}",
        args.join(" "),
        if detail.is_empty() {
            format!("exit status {:?}", output.status.code())
        } else {
            detail
        }
    ))
}

fn systemd_unit_load_state(unit: &str) -> Result<String, String> {
    systemctl(&["show", "--property=LoadState", "--value", unit])
}

fn systemd_unit_file_exists(unit: &str) -> bool {
    [
        format!("/etc/systemd/system/{unit}"),
        format!("/usr/lib/systemd/system/{unit}"),
        format!("/lib/systemd/system/{unit}"),
    ]
    .iter()
    .any(|path| Path::new(path).is_file())
}

fn loaded_systemd_unit(unit: &str) -> Result<bool, String> {
    match systemd_unit_load_state(unit) {
        Ok(state) if state.trim() == "loaded" => Ok(true),
        Ok(_) if systemd_unit_file_exists(unit) => {
            systemctl(&["daemon-reload"])?;
            Ok(systemd_unit_load_state(unit)
                .map(|state| state.trim() == "loaded")
                .unwrap_or(false))
        }
        Ok(_) => Ok(false),
        Err(error) if systemd_unit_file_exists(unit) => {
            systemctl(&["daemon-reload"]).map_err(|reload_error| {
                format!(
                    "{error}. {reload_error}. Service unit file exists, but systemd has not loaded it yet."
                )
            })?;
            Ok(systemd_unit_load_state(unit)
                .map(|state| state.trim() == "loaded")
                .unwrap_or(false))
        }
        Err(error) => Err(error),
    }
}

fn systemd_unit_active(unit: &str) -> bool {
    systemctl(&["is-active", "--quiet", unit]).is_ok()
}

fn loaded_mesh_systemd_units_once() -> (Vec<&'static str>, Vec<String>) {
    let mut loaded = Vec::new();
    let mut errors = Vec::new();

    for unit in MESH_SYSTEMD_UNITS {
        match systemd_unit_load_state(unit) {
            Ok(state) => {
                if state.trim() == "loaded" {
                    loaded.push(*unit);
                }
            }
            Err(error) => errors.push(error),
        }
    }

    (loaded, errors)
}

fn loaded_mesh_systemd_units() -> Result<Vec<&'static str>, String> {
    let (mut loaded, mut errors) = loaded_mesh_systemd_units_once();

    if loaded.is_empty()
        && MESH_SYSTEMD_UNITS
            .iter()
            .any(|unit| systemd_unit_file_exists(unit))
    {
        match systemctl(&["daemon-reload"]) {
            Ok(_) => {
                let retry = loaded_mesh_systemd_units_once();
                loaded = retry.0;
                errors = retry.1;
            }
            Err(error) => errors.push(format!(
                "{error}. Service unit files are installed, but systemd has not reloaded them yet. Run: sudo systemctl daemon-reload"
            )),
        }
    }

    if !loaded.is_empty() {
        return Ok(loaded);
    }
    if errors
        .iter()
        .any(|error| error.contains("systemctl is not available"))
    {
        return Err(errors.join(" | "));
    }

    Err(format!(
        "No controllable x0tta6bl4 mesh systemd unit is installed. Checked: {}. Install/provision the local node service first, then retry from the app.",
        MESH_SYSTEMD_UNITS.join(", ")
    ))
}

fn active_mesh_systemd_units(units: &[&str]) -> Vec<String> {
    units
        .iter()
        .filter_map(|unit| {
            systemctl(&["is-active", "--quiet", unit])
                .ok()
                .map(|_| (*unit).to_string())
        })
        .collect()
}

fn control_mesh_systemd_units(active: bool) -> Result<String, String> {
    let units = loaded_mesh_systemd_units()?;
    let verb = if active { "start" } else { "stop" };
    let mut changed = Vec::new();
    let mut failures = Vec::new();

    for unit in &units {
        match systemctl(&[verb, unit]) {
            Ok(_) => changed.push((*unit).to_string()),
            Err(error) => failures.push(format!("{unit}: {error}")),
        }
    }

    if !failures.is_empty() {
        let hint = format!(
            "If this is a privilege error, run the installed app with a configured polkit/systemd permission or manage the service locally with: sudo systemctl {verb} x0tta6bl4-node.service x0t-agent.service"
        );
        return Err(format!("{} {hint}", failures.join(" | ")));
    }

    thread::sleep(Duration::from_millis(900));
    let active_units = active_mesh_systemd_units(&units);
    Ok(format!(
        "systemd {verb} accepted for {}. Active units after command: {}",
        changed.join(", "),
        if active_units.is_empty() {
            "none".to_string()
        } else {
            active_units.join(", ")
        }
    ))
}

fn capability(
    id: &str,
    label: &str,
    status: &str,
    detail: &str,
    entrypoints: &[&str],
) -> BackendCapability {
    BackendCapability {
        id: id.to_string(),
        label: label.to_string(),
        status: status.to_string(),
        detail: detail.to_string(),
        entrypoints: entrypoints.iter().map(|item| item.to_string()).collect(),
    }
}

fn file_exists(path: &str) -> bool {
    project_root().join(path).is_file()
}

fn collect_backend_capabilities() -> Vec<BackendCapability> {
    let runtime = current_mesh_status();
    let metrics = collect_mesh_metrics();
    let profile_api_online = http_get_local(9472, "/health").is_ok();
    let core_api_online = http_get_local(CORE_API_PORT, "/health").is_ok();
    let full_core_api_online = http_get_local(FULL_CORE_API_PORT, "/health").is_ok()
        || http_get_local(FULL_CORE_API_PORT, "/api/v1/platform/live-snapshot").is_ok();
    let marketplace_online =
        http_get_local(CORE_API_PORT, "/api/v1/maas/marketplace/status").is_ok();
    let billing_online =
        http_get_local(CORE_API_PORT, "/api/v1/maas/billing/billing/plans").is_ok();
    let wallet_online = http_get_local(CORE_API_PORT, "/api/v1/ledger/status").is_ok();
    let governance_online =
        http_get_local(CORE_API_PORT, "/api/v1/maas/governance/readiness").is_ok();
    let agent_health_online =
        http_get_local(CORE_API_PORT, "/api/v1/maas/agents/health/status").is_ok();
    let service_identity_online =
        http_get_local(CORE_API_PORT, "/api/v1/service-identity/status").is_ok();
    let vpn_runtime_online = http_get_local(CORE_API_PORT, "/api/v1/vpn/readiness").is_ok()
        || http_get_local(CORE_API_PORT, "/api/v1/vpn/status").is_ok();
    let provisioning_online =
        http_get_local(CORE_API_PORT, "/api/v1/maas/provisioning/readiness").is_ok();

    vec![
        capability(
            "core_api",
            "Core FastAPI Backend",
            if core_api_online {
                "online"
            } else if file_exists("src/core/app.py") {
                "available"
            } else {
                "missing"
            },
            if core_api_online {
                "Главный backend src.core.app отвечает на локальном loopback-порту 8000."
            } else {
                "Главный backend найден в коде, но сейчас не запущен как локальный API-процесс."
            },
            &["src/core/app.py", "src/api/maas/endpoints/combined.py"],
        ),
        capability(
            "full_core_api",
            "Full Core API",
            if full_core_api_online {
                "online"
            } else if file_exists("src/core/app.py") {
                "available"
            } else {
                "missing"
            },
            if full_core_api_online {
                "Полный backend src.core.app отвечает на отдельном loopback-порту 8001."
            } else {
                "Полный backend доступен в коде, но не запущен; desktop может стартовать его отдельно от быстрого control-plane."
            },
            &["src/core/app.py", "http://127.0.0.1:8001"],
        ),
        capability(
            "mesh_runtime",
            "Local Mesh Runtime",
            if runtime.service_detected && profile_api_online {
                "online"
            } else if runtime.service_detected {
                "state_only"
            } else {
                "missing"
            },
            if runtime.service_detected {
                "Локальное состояние mesh найдено в /opt/x0tta6bl4-mesh/state."
            } else {
                "Локальный mesh runtime не пишет состояние в /opt/x0tta6bl4-mesh/state."
            },
            &[
                "/opt/x0tta6bl4-mesh/scripts/profile_status_api.py",
                "/opt/x0tta6bl4-mesh/state/runtime-state.json",
            ],
        ),
        capability(
            "observability",
            "Observability / VPN Metrics",
            if metrics.ok { "online" } else { "degraded" },
            "Метрики читаются из локальных Prometheus endpoints 127.0.0.1:9090 и 127.0.0.1:9091.",
            &["/opt/x0tta6bl4-mesh/scripts/monitor.py", "http://127.0.0.1:9090", "http://127.0.0.1:9091"],
        ),
        capability(
            "mapek",
            "MAPE-K Self-Healing",
            if agent_health_online {
                "online"
            } else if file_exists("src/self_healing/mape_k_integrated.py") {
                "source_available"
            } else {
                "missing"
            },
            "Код контура самовосстановления есть в репозитории; desktop пока подключает статус, а не запускает healing-действия.",
            &[
                "src/self_healing/mape_k_integrated.py",
                "src/self_healing/mape_k/manager.py",
            ],
        ),
        capability(
            "graphsage",
            "GraphSAGE Anomaly Detector",
            if file_exists("src/ml/graphsage_anomaly_detector.py") {
                "source_available"
            } else {
                "missing"
            },
            "Детектор аномалий и observe-mode есть в кодовой базе; нужен отдельный runtime-процесс для live inference.",
            &[
                "src/ml/graphsage_anomaly_detector.py",
                "src/ml/graphsage_observe_mode.py",
            ],
        ),
        capability(
            "maas_marketplace",
            "MaaS Marketplace",
            if marketplace_online {
                "online"
            } else if file_exists("src/api/maas/endpoints/marketplace.py") {
                "source_available"
            } else {
                "missing"
            },
            "API marketplace есть; desktop package пока не поднимает MaaS API и базу данных автоматически.",
            &[
                "src/api/maas/endpoints/marketplace.py",
                "src/services/marketplace_settlement.py",
            ],
        ),
        capability(
            "billing",
            "Billing / Subscriptions",
            if billing_online {
                "online"
            } else if file_exists("src/api/maas/endpoints/billing.py") {
                "source_available"
            } else {
                "missing"
            },
            "Billing API есть; для реальных платежей нужны локальные env-настройки и внешний платежный провайдер.",
            &["src/api/maas/endpoints/billing.py", "src/api/billing.py"],
        ),
        capability(
            "wallet_rewards",
            "Wallet / Rewards",
            if wallet_online {
                "online"
            } else if file_exists("src/services/reward_events.py") {
                "source_available"
            } else {
                "missing"
            },
            "Reward events и DAO token modules есть; desktop не показывает фейковый баланс без подключенного wallet backend.",
            &["src/services/reward_events.py", "src/dao/token_rewards.py"],
        ),
        capability(
            "dao_governance",
            "DAO Governance",
            if governance_online {
                "online"
            } else if file_exists("src/api/maas/endpoints/governance.py") {
                "source_available"
            } else {
                "missing"
            },
            "Governance API и executor есть; выполнение proposal требует настроенного signer/chain окружения.",
            &[
                "src/api/maas/endpoints/governance.py",
                "src/dao/executor_webhook.py",
            ],
        ),
        capability(
            "service_identity",
            "Service Identity / SPIFFE",
            if service_identity_online {
                "online"
            } else if file_exists("src/api/maas/endpoints/service_identity_status.py") {
                "source_available"
            } else {
                "missing"
            },
            "Service identity API показывает redacted SPIFFE/DID/wallet/event identity surfaces без раскрытия секретов.",
            &[
                "src/api/maas/endpoints/service_identity_status.py",
                "src/services/service_identity_registry.py",
            ],
        ),
        capability(
            "vpn_runtime",
            "VPN / Transport",
            if vpn_runtime_online {
                "online"
            } else if file_exists("src/api/maas/endpoints/vpn.py") {
                "source_available"
            } else {
                "missing"
            },
            "VPN API показывает readiness/status и админские user surfaces через full-core auth.",
            &[
                "src/api/maas/endpoints/vpn.py",
                "src/network/vpn_leak_protection.py",
            ],
        ),
        capability(
            "maas_provisioning",
            "MaaS Provisioning",
            if provisioning_online {
                "online"
            } else if file_exists("src/api/maas/endpoints/provisioning.py") {
                "source_available"
            } else {
                "missing"
            },
            "Provisioning API генерирует node setup package и pending-node evidence, но не доказывает фактический dataplane join.",
            &[
                "src/api/maas/endpoints/provisioning.py",
                "src/services/provisioning_service.py",
            ],
        ),
        capability(
            "readiness_gate",
            "Real Readiness Gate",
            if file_exists("scripts/ops/check_real_readiness.py") {
                "available"
            } else {
                "missing"
            },
            "Локальная проверка готовности проекта доступна из приложения как диагностический снимок.",
            &["scripts/ops/check_real_readiness.py"],
        ),
    ]
}

fn process_exists(pid: u32) -> bool {
    Command::new("kill")
        .arg("-0")
        .arg(pid.to_string())
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

fn python_binary() -> String {
    let venv_python = project_root().join(".venv/bin/python");
    if venv_python.is_file() {
        venv_python.to_string_lossy().to_string()
    } else {
        "python3".to_string()
    }
}

fn core_api_app_module() -> String {
    std::env::var("X0TTA6BL4_CORE_API_APP_MODULE")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| DEFAULT_CORE_API_APP_MODULE.to_string())
}

fn full_core_api_app_module() -> String {
    std::env::var("X0TTA6BL4_FULL_CORE_API_APP_MODULE")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .unwrap_or_else(|| DEFAULT_FULL_CORE_API_APP_MODULE.to_string())
}

fn core_api_module_source_path(module_spec: &str) -> PathBuf {
    let module_name = module_spec.split(':').next().unwrap_or(module_spec);
    project_root().join(format!("{}.py", module_name.replace('.', "/")))
}

fn should_use_packaged_desktop_core_api(port: u16, app_module: &str) -> bool {
    port == CORE_API_PORT
        && app_module == DEFAULT_CORE_API_APP_MODULE
        && Path::new(PACKAGED_DESKTOP_CORE_API_PATH).is_file()
}

fn tail_log(path: &str, limit: usize) -> Option<String> {
    let body = fs::read_to_string(path).ok()?;
    let lines = body.lines().rev().take(limit).collect::<Vec<&str>>();
    Some(lines.into_iter().rev().collect::<Vec<&str>>().join("\n"))
}

fn read_pid(path: &str) -> Option<u32> {
    let body = fs::read_to_string(path).ok()?;
    body.trim().parse::<u32>().ok()
}

fn current_api_status(port: u16, pid_path: &str, log_path: &str, label: &str) -> CoreApiStatus {
    let health_result = http_get_local(port, "/health");
    let status_path = if port == FULL_CORE_API_PORT {
        "/api/v1/platform/live-snapshot"
    } else {
        "/status"
    };
    let status_result = http_get_local(port, status_path);
    let health_ok = health_result.is_ok();
    let status_ok = status_result.is_ok();
    let pid = read_pid(pid_path).filter(|pid| process_exists(*pid));
    let running = health_ok || status_ok;
    let log_tail = tail_log(log_path, 8);

    CoreApiStatus {
        running,
        base_url: format!("http://127.0.0.1:{port}"),
        health_ok,
        status_ok,
        pid,
        log_path: log_path.to_string(),
        message: if running {
            format!("{label} is reachable.")
        } else if pid.is_some() {
            format!("{label} process exists, but HTTP health is not ready yet.")
        } else {
            format!("{label} is not reachable on 127.0.0.1:{port}.")
        },
        error: if running {
            None
        } else {
            Some(log_tail.unwrap_or_else(|| {
                format!("No local response from {label} and no startup log is available yet.")
            }))
        },
    }
}

fn current_core_api_status() -> CoreApiStatus {
    current_api_status(
        CORE_API_PORT,
        CORE_API_PID_PATH,
        CORE_API_LOG_PATH,
        "Desktop Core API",
    )
}

fn current_full_core_api_status() -> CoreApiStatus {
    current_api_status(
        FULL_CORE_API_PORT,
        FULL_CORE_API_PID_PATH,
        FULL_CORE_API_LOG_PATH,
        "Full Core API",
    )
}

fn control_api_systemd_unit(
    unit: &str,
    port: u16,
    pid_path: &str,
    log_path: &str,
    label: &str,
    active: bool,
    wait_attempts: usize,
) -> Result<CoreApiStatus, String> {
    if !loaded_systemd_unit(unit)? {
        return Err(format!(
            "{unit} is not installed. Falling back to app-owned process startup."
        ));
    }

    let verb = if active { "start" } else { "stop" };
    systemctl(&[verb, unit]).map_err(|error| {
        format!(
            "{error}. If this is a privilege error, manage the service locally with: sudo systemctl {verb} {unit}"
        )
    })?;

    for _ in 0..wait_attempts {
        thread::sleep(Duration::from_millis(500));
        let reachable = http_get_local(port, "/health").is_ok()
            || http_get_local(port, "/api/v1/platform/live-snapshot").is_ok();
        if (active && reachable) || (!active && !reachable && !systemd_unit_active(unit)) {
            break;
        }
    }

    Ok(current_api_status(port, pid_path, log_path, label))
}

fn control_core_api_systemd_unit(active: bool, wait_attempts: usize) -> Result<CoreApiStatus, String> {
    control_api_systemd_unit(
        CORE_API_SYSTEMD_UNIT,
        CORE_API_PORT,
        CORE_API_PID_PATH,
        CORE_API_LOG_PATH,
        "Desktop Core API",
        active,
        wait_attempts,
    )
}

fn control_full_core_api_systemd_unit(active: bool, wait_attempts: usize) -> Result<CoreApiStatus, String> {
    control_api_systemd_unit(
        FULL_CORE_API_SYSTEMD_UNIT,
        FULL_CORE_API_PORT,
        FULL_CORE_API_PID_PATH,
        FULL_CORE_API_LOG_PATH,
        "Full Core API",
        active,
        wait_attempts,
    )
}

fn summarize_json_response(value: &Value) -> (Option<String>, String) {
    let status = value
        .get("status")
        .or_else(|| value.get("state"))
        .or_else(|| value.get("decision"))
        .or_else(|| value.get("health"))
        .and_then(Value::as_str)
        .map(str::to_string);

    let keys = value
        .as_object()
        .map(|object| {
            object
                .keys()
                .take(8)
                .map(String::as_str)
                .collect::<Vec<&str>>()
                .join(", ")
        })
        .unwrap_or_else(|| value.to_string().chars().take(160).collect::<String>());

    (status, format!("keys: {keys}"))
}

fn probe_api_endpoints(port: u16, endpoints: &[(&str, &str)]) -> Vec<CoreApiEndpointProbe> {
    endpoints
        .iter()
        .map(|(label, path)| match http_get_local(port, path) {
            Ok(body) => match serde_json::from_str::<Value>(&body) {
                Ok(value) => {
                    let (status, detail) = summarize_json_response(&value);
                    CoreApiEndpointProbe {
                        label: label.to_string(),
                        path: path.to_string(),
                        ok: true,
                        status,
                        detail,
                        error: None,
                    }
                }
                Err(error) => CoreApiEndpointProbe {
                    label: label.to_string(),
                    path: path.to_string(),
                    ok: true,
                    status: None,
                    detail: body.chars().take(160).collect::<String>(),
                    error: Some(format!("non-json response: {error}")),
                },
            },
            Err(error) => CoreApiEndpointProbe {
                label: label.to_string(),
                path: path.to_string(),
                ok: false,
                status: None,
                detail: "endpoint is not reachable".to_string(),
                error: Some(error),
            },
        })
        .collect()
}

fn core_api_endpoint_probes() -> Vec<CoreApiEndpointProbe> {
    let endpoints = [
        ("Health", "/health"),
        ("Ready", "/health/ready"),
        ("Status", "/status"),
        ("Live Snapshot", "/api/v1/platform/live-snapshot"),
        ("Mesh Status", "/mesh/status"),
        ("Mesh Peers", "/mesh/peers"),
        ("Actions", "/api/v1/actions"),
        ("MaaS Marketplace", "/api/v1/maas/marketplace/status"),
        ("Billing Plans", "/api/v1/maas/billing/billing/plans"),
        ("Billing Usage", "/api/v1/maas/billing/usage"),
        ("Governance", "/api/v1/maas/governance/readiness"),
        ("VPN", "/api/v1/vpn/readiness"),
        ("Ledger", "/api/v1/ledger/status"),
        ("Service Identity", "/api/v1/service-identity/status"),
        ("Agent Mesh", "/api/v1/maas/agents/health/status"),
    ];
    probe_api_endpoints(CORE_API_PORT, &endpoints)
}

fn full_core_api_endpoint_probes() -> Vec<CoreApiEndpointProbe> {
    let endpoints = [
        ("Health", "/health"),
        ("Ready", "/health/ready"),
        ("Live Snapshot", "/api/v1/platform/live-snapshot"),
        ("Billing Plans", "/api/v1/maas/billing/billing/plans"),
    ];
    probe_api_endpoints(FULL_CORE_API_PORT, &endpoints)
}

fn current_mesh_status() -> MeshRuntimeStatus {
    let runtime = read_json(RUNTIME_STATE_PATH);
    let hint = read_json(CLIENT_PROFILE_HINT_PATH);
    let signal = read_json(LISTENER_SIGNAL_PATH);
    let hot_path = runtime
        .as_ref()
        .and_then(|item| item.get("hot_path_summary"))
        .filter(|item| item.is_object());

    let runtime_mode = string_at(runtime.as_ref(), "mode")
        .or_else(|| string_at(hot_path, "runtime_mode"))
        .or_else(|| string_at(hint.as_ref(), "runtime_mode"));
    let recommended_action = string_at(runtime.as_ref(), "recommended_action")
        .or_else(|| string_at(hot_path, "recommended_action"))
        .or_else(|| string_at(hint.as_ref(), "recommended_action"));
    let listener_signal_status = string_at(signal.as_ref(), "status");
    let best_path =
        string_at(hot_path, "best_path").or_else(|| string_at(hint.as_ref(), "best_path"));
    let best_path_port =
        u64_at(hot_path, "best_path_port").or_else(|| u64_at(hint.as_ref(), "best_path_port"));

    let service_detected = runtime.is_some() || hint.is_some() || signal.is_some();
    let listener_ok = listener_signal_status
        .as_deref()
        .map(|status| status == "BASELINE_OK")
        .unwrap_or(false);
    let stopped = recommended_action
        .as_deref()
        .map(|action| action == "stopped")
        .unwrap_or(false)
        || runtime_mode
            .as_deref()
            .map(|mode| mode.contains("stopping") || mode.contains("stopped"))
            .unwrap_or(false);
    let active = service_detected && runtime_mode.is_some() && !stopped;
    let ok = active && listener_ok;

    let mut logs = Vec::new();
    if service_detected {
        logs.push("[RUNTIME] local x0tta6bl4 mesh state found".to_string());
    } else {
        logs.push("[RUNTIME] local x0tta6bl4 mesh state not found".to_string());
    }
    if let Some(mode) = &runtime_mode {
        logs.push(format!("[MODE] {mode}"));
    }
    if let Some(profile) = string_at(hint.as_ref(), "recommended_profile") {
        logs.push(format!("[PROFILE] {profile}"));
    }
    if let Some(action) = &recommended_action {
        logs.push(format!("[ACTION] {action}"));
    }

    MeshRuntimeStatus {
        active,
        ok,
        service_detected,
        runtime_mode,
        recommended_action,
        recommended_profile: string_at(hint.as_ref(), "recommended_profile"),
        best_path,
        best_path_port,
        transport_health_status: string_at(hot_path, "transport_health_status")
            .or_else(|| string_at(hint.as_ref(), "transport_health_status")),
        subscription_health_status: string_at(hot_path, "subscription_health_status")
            .or_else(|| string_at(hint.as_ref(), "subscription_health_status")),
        listener_signal_status,
        primary_path_latency_s: f64_at(hot_path, "primary_path_latency_s"),
        secondary_path_latency_s: f64_at(hot_path, "secondary_path_latency_s"),
        fallback_nl_path_latency_s: f64_at(hot_path, "fallback_nl_path_latency_s"),
        error: if service_detected {
            None
        } else {
            Some(format!(
                "Local runtime state is missing. Expected {RUNTIME_STATE_PATH}, {CLIENT_PROFILE_HINT_PATH}, and {LISTENER_SIGNAL_PATH}."
            ))
        },
        logs,
    }
}

#[tauri::command]
async fn mesh_status() -> Result<MeshRuntimeStatus, String> {
    Ok(current_mesh_status())
}

#[tauri::command]
async fn runtime_metrics() -> Result<MeshMetricsSummary, String> {
    Ok(collect_mesh_metrics())
}

#[tauri::command]
async fn backend_capabilities() -> Result<Vec<BackendCapability>, String> {
    Ok(collect_backend_capabilities())
}

#[tauri::command]
async fn core_api_status() -> Result<CoreApiStatus, String> {
    Ok(current_core_api_status())
}

#[tauri::command]
async fn core_api_probes() -> Result<Vec<CoreApiEndpointProbe>, String> {
    Ok(core_api_endpoint_probes())
}

#[tauri::command]
async fn core_api_get(path: String) -> Result<Value, String> {
    validate_core_api_path(&path)?;
    let body = http_get_local(CORE_API_PORT, &path)?;
    serde_json::from_str::<Value>(&body).map_err(|error| {
        format!(
            "Core API response for {path} is not JSON: {error}. Body prefix: {}",
            body.chars().take(180).collect::<String>()
        )
    })
}

#[tauri::command]
async fn core_api_post(path: String, payload: Value) -> Result<Value, String> {
    validate_core_api_path(&path)?;
    let body = http_post_local(CORE_API_PORT, &path, &payload)?;
    serde_json::from_str::<Value>(&body).map_err(|error| {
        format!(
            "Core API POST response for {path} is not JSON: {error}. Body prefix: {}",
            body.chars().take(180).collect::<String>()
        )
    })
}

#[tauri::command]
async fn full_core_api_get(
    path: String,
    auth: Option<CoreApiAuthHeaders>,
) -> Result<Value, String> {
    validate_core_api_path(&path)?;
    let headers = auth_header_lines(auth)?;
    let body = http_get_local_with_headers(FULL_CORE_API_PORT, &path, &headers)?;
    serde_json::from_str::<Value>(&body).map_err(|error| {
        format!(
            "Full Core API response for {path} is not JSON: {error}. Body prefix: {}",
            body.chars().take(180).collect::<String>()
        )
    })
}

#[tauri::command]
async fn full_core_api_post(
    path: String,
    payload: Value,
    auth: Option<CoreApiAuthHeaders>,
) -> Result<Value, String> {
    validate_core_api_path(&path)?;
    let headers = auth_header_lines(auth)?;
    let body = http_post_local_with_headers(FULL_CORE_API_PORT, &path, &payload, &headers)?;
    serde_json::from_str::<Value>(&body).map_err(|error| {
        format!(
            "Full Core API POST response for {path} is not JSON: {error}. Body prefix: {}",
            body.chars().take(180).collect::<String>()
        )
    })
}

fn start_api_process(
    port: u16,
    pid_path: &str,
    log_path: &str,
    app_module: String,
    label: &str,
    wait_attempts: usize,
) -> Result<CoreApiStatus, String> {
    let current = current_api_status(port, pid_path, log_path, label);
    if current.running {
        return Ok(current);
    }

    let log_file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
        .map_err(|error| error.to_string())?;
    let log_file_for_stderr = log_file.try_clone().map_err(|error| error.to_string())?;

    if should_use_packaged_desktop_core_api(port, &app_module) {
        let child = Command::new("python3")
            .arg(PACKAGED_DESKTOP_CORE_API_PATH)
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(port.to_string())
            .stdout(Stdio::from(log_file))
            .stderr(Stdio::from(log_file_for_stderr))
            .spawn()
            .map_err(|error| error.to_string())?;

        let pid = child.id();
        let mut pid_file = File::create(pid_path).map_err(|error| error.to_string())?;
        writeln!(pid_file, "{pid}").map_err(|error| error.to_string())?;

        for _ in 0..wait_attempts {
            thread::sleep(Duration::from_millis(500));
            if http_get_local(port, "/health").is_ok()
                || http_get_local(port, "/api/v1/platform/live-snapshot").is_ok()
            {
                break;
            }
        }
        return Ok(current_api_status(port, pid_path, log_path, label));
    }

    let app_module_source = core_api_module_source_path(&app_module);
    if !app_module_source.is_file() {
        return Ok(CoreApiStatus {
            running: false,
            base_url: format!("http://127.0.0.1:{port}"),
            health_ok: false,
            status_ok: false,
            pid: None,
            log_path: log_path.to_string(),
            message: format!("{label} source file is missing."),
            error: Some(format!(
                "{} not found for app module {app_module}",
                app_module_source.display()
            )),
        });
    }

    let root = project_root();
    let child = Command::new(python_binary())
        .arg("-m")
        .arg("uvicorn")
        .arg(app_module)
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&root)
        .env("PYTHONPATH", root.to_string_lossy().to_string())
        .env("MAAS_LIGHT_MODE", "true")
        .stdout(Stdio::from(log_file))
        .stderr(Stdio::from(log_file_for_stderr))
        .spawn()
        .map_err(|error| error.to_string())?;

    let pid = child.id();
    let mut pid_file = File::create(pid_path).map_err(|error| error.to_string())?;
    writeln!(pid_file, "{pid}").map_err(|error| error.to_string())?;

    for _ in 0..wait_attempts {
        thread::sleep(Duration::from_millis(500));
        if http_get_local(port, "/health").is_ok()
            || http_get_local(port, "/api/v1/platform/live-snapshot").is_ok()
        {
            break;
        }
    }
    Ok(current_api_status(port, pid_path, log_path, label))
}

fn stop_api_process(port: u16, pid_path: &str, log_path: &str, label: &str) -> CoreApiStatus {
    if let Some(pid) = read_pid(pid_path) {
        let _ = Command::new("kill")
            .arg("-TERM")
            .arg(pid.to_string())
            .output();
        thread::sleep(Duration::from_millis(800));
        if process_exists(pid) {
            let _ = Command::new("kill")
                .arg("-KILL")
                .arg(pid.to_string())
                .output();
        }
        let _ = fs::remove_file(pid_path);
        thread::sleep(Duration::from_millis(300));
    }
    current_api_status(port, pid_path, log_path, label)
}

#[tauri::command]
async fn start_core_api() -> Result<CoreApiStatus, String> {
    let app_module = core_api_app_module();
    if should_use_packaged_desktop_core_api(CORE_API_PORT, &app_module)
        && systemd_unit_file_exists(CORE_API_SYSTEMD_UNIT)
    {
        match control_core_api_systemd_unit(true, 16) {
            Ok(status) => return Ok(status),
            Err(systemd_error) => {
                let mut status = start_api_process(
                    CORE_API_PORT,
                    CORE_API_PID_PATH,
                    CORE_API_LOG_PATH,
                    app_module,
                    "Desktop Core API",
                    16,
                )?;
                status.message = format!(
                    "{} Systemd start failed; app-owned fallback process was attempted.",
                    status.message
                );
                status.error = Some(systemd_error);
                return Ok(status);
            }
        }
    }

    start_api_process(
        CORE_API_PORT,
        CORE_API_PID_PATH,
        CORE_API_LOG_PATH,
        app_module,
        "Desktop Core API",
        16,
    )
}

#[tauri::command]
async fn stop_core_api() -> Result<CoreApiStatus, String> {
    let systemd_error = if systemd_unit_file_exists(CORE_API_SYSTEMD_UNIT) {
        control_core_api_systemd_unit(false, 8).err()
    } else {
        None
    };
    let mut status = stop_api_process(
        CORE_API_PORT,
        CORE_API_PID_PATH,
        CORE_API_LOG_PATH,
        "Desktop Core API",
    );
    if let Some(error) = systemd_error {
        status.error = Some(error);
    }
    Ok(status)
}

#[tauri::command]
async fn full_core_api_status() -> Result<CoreApiStatus, String> {
    Ok(current_full_core_api_status())
}

#[tauri::command]
async fn full_core_api_probes() -> Result<Vec<CoreApiEndpointProbe>, String> {
    Ok(full_core_api_endpoint_probes())
}

#[tauri::command]
async fn start_full_core_api() -> Result<CoreApiStatus, String> {
    let app_module = full_core_api_app_module();
    if app_module == DEFAULT_FULL_CORE_API_APP_MODULE
        && systemd_unit_file_exists(FULL_CORE_API_SYSTEMD_UNIT)
    {
        match control_full_core_api_systemd_unit(true, 120) {
            Ok(status) => return Ok(status),
            Err(systemd_error) => {
                let mut status = start_api_process(
                    FULL_CORE_API_PORT,
                    FULL_CORE_API_PID_PATH,
                    FULL_CORE_API_LOG_PATH,
                    app_module,
                    "Full Core API",
                    120,
                )?;
                status.message = format!(
                    "{} Systemd start failed; app-owned fallback process was attempted.",
                    status.message
                );
                status.error = Some(systemd_error);
                return Ok(status);
            }
        }
    }

    start_api_process(
        FULL_CORE_API_PORT,
        FULL_CORE_API_PID_PATH,
        FULL_CORE_API_LOG_PATH,
        app_module,
        "Full Core API",
        120,
    )
}

#[tauri::command]
async fn stop_full_core_api() -> Result<CoreApiStatus, String> {
    let systemd_error = if systemd_unit_file_exists(FULL_CORE_API_SYSTEMD_UNIT) {
        control_full_core_api_systemd_unit(false, 8).err()
    } else {
        None
    };
    let mut status = stop_api_process(
        FULL_CORE_API_PORT,
        FULL_CORE_API_PID_PATH,
        FULL_CORE_API_LOG_PATH,
        "Full Core API",
    );
    if let Some(error) = systemd_error {
        status.error = Some(error);
    }
    Ok(status)
}

#[tauri::command]
async fn readiness_snapshot() -> Result<ReadinessSnapshot, String> {
    let root = project_root();
    if !root.join("scripts/ops/check_real_readiness.py").is_file() {
        return Ok(ReadinessSnapshot {
            ok: false,
            ready: None,
            decision: None,
            passed: None,
            failures: None,
            warnings: None,
            blocker_ids: Vec::new(),
            error: Some(format!(
                "Readiness script not found under {}/scripts/ops/check_real_readiness.py",
                project_root_display()
            )),
        });
    }

    let output = Command::new("timeout")
        .arg("45s")
        .arg("python3")
        .arg("scripts/ops/check_real_readiness.py")
        .arg("--skip-command-checks")
        .arg("--skip-git-check")
        .arg("--json")
        .current_dir(&root)
        .output()
        .map_err(|error| error.to_string())?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let parsed: Value = match serde_json::from_str(&stdout) {
        Ok(value) => value,
        Err(error) => {
            let details = if stderr.trim().is_empty() {
                stdout.chars().take(600).collect::<String>()
            } else {
                stderr.chars().take(600).collect::<String>()
            };
            return Ok(ReadinessSnapshot {
                ok: false,
                ready: None,
                decision: None,
                passed: None,
                failures: None,
                warnings: None,
                blocker_ids: Vec::new(),
                error: Some(format!(
                    "Readiness output is not valid JSON: {error}. {details}"
                )),
            });
        }
    };

    let summary = parsed.get("summary");
    let blocker_ids = parsed
        .get("blockers")
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(|item| {
                    item.get("check_id")
                        .or_else(|| item.get("id"))
                        .and_then(Value::as_str)
                        .map(str::to_string)
                })
                .take(12)
                .collect::<Vec<String>>()
        })
        .unwrap_or_default();

    Ok(ReadinessSnapshot {
        ok: parsed
            .get("ready")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        ready: parsed.get("ready").and_then(Value::as_bool),
        decision: string_at(Some(&parsed), "decision"),
        passed: u64_at(summary, "passed"),
        failures: u64_at(summary, "failures"),
        warnings: u64_at(summary, "warnings"),
        blocker_ids,
        error: if output.status.success() {
            None
        } else {
            Some(format!(
                "Readiness command exited with status {:?}",
                output.status.code()
            ))
        },
    })
}

#[tauri::command]
async fn set_mesh_active(active: bool) -> Result<MeshToggleResult, String> {
    match control_mesh_systemd_units(active) {
        Ok(message) => {
            let mut status = current_mesh_status();
            status.logs.push(format!("[SYSTEMD] {message}"));
            Ok(MeshToggleResult {
                success: true,
                active: status.active,
                message,
                status,
            })
        }
        Err(error) => {
            let mut status = current_mesh_status();
            status.logs.push(format!("[SYSTEMD] {error}"));
            Ok(MeshToggleResult {
                success: false,
                active: status.active,
                message: error,
                status,
            })
        }
    }
}

#[tauri::command]
async fn toggle_mesh(active: bool) -> Result<String, String> {
    let python_cmd = "python3";
    let bridge_path = "src/client/bridge.py";

    if !Path::new(bridge_path).is_file() {
        return Err(format!("Bridge script not found at {bridge_path}"));
    }

    if active {
        println!("Starting x0tta6bl4 mesh bridge...");

        let output = Command::new(python_cmd)
            .arg(bridge_path)
            .arg("connect")
            .output()
            .map_err(|e| e.to_string())?;

        let stdout = String::from_utf8_lossy(&output.stdout);
        println!("Bridge Output: {}", stdout);

        let v: Value = serde_json::from_str(&stdout).map_err(|e| e.to_string())?;
        if v["success"].as_bool().unwrap_or(false) {
            Ok("Mesh connected".to_string())
        } else {
            Err("Mesh authentication or connection failed".to_string())
        }
    } else {
        println!("Stopping x0tta6bl4 mesh bridge...");
        Command::new(python_cmd)
            .arg(bridge_path)
            .arg("stop")
            .output()
            .map_err(|e| e.to_string())?;

        Ok("Mesh disconnected".to_string())
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            mesh_status,
            runtime_metrics,
            backend_capabilities,
            core_api_status,
            core_api_probes,
            core_api_get,
            core_api_post,
            full_core_api_status,
            full_core_api_probes,
            full_core_api_get,
            full_core_api_post,
            start_core_api,
            stop_core_api,
            start_full_core_api,
            stop_full_core_api,
            readiness_snapshot,
            set_mesh_active,
            toggle_mesh
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
