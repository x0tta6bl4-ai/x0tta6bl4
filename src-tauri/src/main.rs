#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;
use serde_json::Value;

#[tauri::command]
async fn toggle_mesh(active: bool) -> Result<String, String> {
    let python_cmd = "python3";
    let bridge_path = "src/client/bridge.py";

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
        .invoke_handler(tauri::generate_handler![toggle_mesh])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
