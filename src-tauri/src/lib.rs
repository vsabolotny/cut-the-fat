use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;
use tokio::sync::OnceCell;
use std::sync::Arc;

/// Shared state: holds the dynamically assigned backend port.
struct BackendState {
    port: OnceCell<u16>,
}

/// IPC command: frontend calls this to get the backend port.
/// Waits up to 30s for the sidecar to signal READY.
#[tauri::command]
async fn get_backend_port(state: tauri::State<'_, Arc<BackendState>>) -> Result<u16, String> {
    match tokio::time::timeout(
        std::time::Duration::from_secs(30),
        state.port.wait(),
    )
    .await
    {
        Ok(port) => Ok(*port),
        Err(_) => Err("Backend-Timeout: Sidecar hat nicht rechtzeitig geantwortet.".into()),
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .setup(|app| {
            let state = Arc::new(BackendState {
                port: OnceCell::new(),
            });
            app.manage(state.clone());

            // Pick a free port for the Python sidecar
            let port = portpicker::pick_unused_port().expect("Kein freier Port gefunden");

            // Spawn the Python sidecar with the port as argument
            let (mut rx, child) = app
                .shell()
                .sidecar("ctf-sidecar")
                .expect("Sidecar 'ctf-sidecar' nicht gefunden")
                .args([port.to_string()])
                .spawn()
                .expect("Sidecar konnte nicht gestartet werden");

            // IMPORTANT: keep child handle alive — dropping it kills the sidecar
            app.manage(child);

            // Listen for the READY signal from the sidecar's stdout
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let line = String::from_utf8_lossy(&line);
                            let trimmed = line.trim();
                            if trimmed.starts_with("READY:") {
                                if let Ok(p) = trimmed[6..].parse::<u16>() {
                                    let _ = state.port.set(p);
                                }
                            }
                        }
                        CommandEvent::Stderr(line) => {
                            let line = String::from_utf8_lossy(&line);
                            eprintln!("[sidecar stderr] {}", line.trim());
                        }
                        _ => {}
                    }
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Fehler beim Starten der Tauri-App");
}
