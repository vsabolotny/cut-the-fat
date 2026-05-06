use tauri::Manager;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_shell::process::CommandEvent;
use tokio::sync::watch;
use std::sync::Arc;

struct BackendState {
    port_rx: watch::Receiver<Option<u16>>,
}

/// IPC command: frontend calls this to get the backend port.
/// Waits up to 30s for the sidecar to signal READY.
#[tauri::command]
async fn get_backend_port(state: tauri::State<'_, Arc<BackendState>>) -> Result<u16, String> {
    let mut rx = state.port_rx.clone();
    match tokio::time::timeout(
        std::time::Duration::from_secs(30),
        async move {
            loop {
                if let Some(port) = *rx.borrow() {
                    return Ok(port);
                }
                rx.changed().await.map_err(|_| "channel closed".to_string())?;
            }
        },
    )
    .await
    {
        Ok(Ok(port)) => Ok(port),
        Ok(Err(e)) => Err(e),
        Err(_) => Err("Backend-Timeout: Sidecar hat nicht rechtzeitig geantwortet.".into()),
    }
}

pub fn run() {
    let (port_tx, port_rx) = watch::channel(None::<u16>);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![get_backend_port])
        .setup(move |app| {
            app.manage(Arc::new(BackendState { port_rx }));

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
                                    let _ = port_tx.send(Some(p));
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
