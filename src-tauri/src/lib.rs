use std::sync::Arc;

use tauri::Manager;
use tauri_plugin_dialog::{DialogExt, MessageDialogButtons};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;
use tauri_plugin_updater::UpdaterExt;
use tokio::sync::watch;
use uuid::Uuid;

#[derive(Clone, serde::Serialize)]
struct BackendInfo {
    port: u16,
    token: String,
}

struct BackendState {
    info_rx: watch::Receiver<Option<BackendInfo>>,
}

/// IPC command: frontend calls this to get the backend port + auth token.
/// Waits up to 30s for the sidecar to signal READY.
#[tauri::command]
async fn get_backend_info(
    state: tauri::State<'_, Arc<BackendState>>,
) -> Result<BackendInfo, String> {
    let mut rx = state.info_rx.clone();
    match tokio::time::timeout(std::time::Duration::from_secs(30), async move {
        loop {
            if let Some(info) = rx.borrow().clone() {
                return Ok::<BackendInfo, String>(info);
            }
            rx.changed()
                .await
                .map_err(|_| "channel closed".to_string())?;
        }
    })
    .await
    {
        Ok(Ok(info)) => Ok(info),
        Ok(Err(e)) => Err(e),
        Err(_) => Err("Backend-Timeout: Sidecar hat nicht rechtzeitig geantwortet.".into()),
    }
}

async fn check_for_updates(app: tauri::AppHandle) {
    // Wait a few seconds so the app window is fully shown before any dialog
    tokio::time::sleep(std::time::Duration::from_secs(5)).await;

    let updater = match app.updater() {
        Ok(u) => u,
        Err(_) => return,
    };

    let update = match updater.check().await {
        Ok(Some(u)) => u,
        _ => return,
    };

    let version = update.version.clone();
    let notes = update.body.clone().unwrap_or_default();
    let msg = if notes.trim().is_empty() {
        format!("Version {} ist verfügbar.\n\nJetzt aktualisieren?", version)
    } else {
        format!(
            "Version {} ist verfügbar.\n\n{}\n\nJetzt aktualisieren?",
            version,
            notes.trim()
        )
    };

    // Run blocking_show on a dedicated blocking thread so we never park a
    // tokio worker thread on a synchronous UI dialog.
    let app_for_dialog = app.clone();
    let confirmed = tauri::async_runtime::spawn_blocking(move || {
        app_for_dialog
            .dialog()
            .message(msg)
            .title("Update verfügbar")
            .buttons(MessageDialogButtons::OkCancelCustom(
                "Jetzt installieren".into(),
                "Später".into(),
            ))
            .blocking_show()
    })
    .await
    .unwrap_or(false);

    if !confirmed {
        return;
    }

    let _ = update
        .download_and_install(|_chunk, _total| {}, || {})
        .await;

    // Restart to apply the update
    app.restart();
}

pub fn run() {
    let (info_tx, info_rx) = watch::channel::<Option<BackendInfo>>(None);

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![get_backend_info])
        .setup(move |app| {
            app.manage(Arc::new(BackendState { info_rx }));

            // Check for updates in the background (non-blocking)
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                check_for_updates(handle).await;
            });

            // Pick a free port and an auth token for the Python sidecar.
            let port = portpicker::pick_unused_port().expect("Kein freier Port gefunden");
            let token = Uuid::new_v4().to_string();
            let token_for_state = token.clone();

            // Spawn the Python sidecar with port as arg and the auth token
            // as an env var. The sidecar uses it to gate /api/* and /ws/chat.
            let (mut rx, child) = app
                .shell()
                .sidecar("ctf-sidecar")
                .expect("Sidecar 'ctf-sidecar' nicht gefunden")
                .args([port.to_string()])
                .env("CTF_AUTH_TOKEN", token.clone())
                .spawn()
                .expect("Sidecar konnte nicht gestartet werden");

            // IMPORTANT: keep child handle alive — dropping it kills the sidecar
            app.manage(child);

            // Listen for the READY signal from the sidecar's stdout.
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(line) => {
                            let line = String::from_utf8_lossy(&line);
                            let trimmed = line.trim();
                            if trimmed.starts_with("READY:") {
                                if let Ok(p) = trimmed[6..].parse::<u16>() {
                                    let _ = info_tx.send(Some(BackendInfo {
                                        port: p,
                                        token: token_for_state.clone(),
                                    }));
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
