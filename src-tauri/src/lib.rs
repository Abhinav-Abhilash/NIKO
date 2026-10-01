use std::process::{Child, Command};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::Manager;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

static BACKEND_CHILD: Mutex<Option<Child>> = Mutex::new(None);
static IS_BACKEND_SPAWNED: AtomicBool = AtomicBool::new(false);

fn get_workspace_root() -> std::path::PathBuf {
    let cwd = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));
    if cwd.join("backend").join("app").join("main.py").exists() {
        return cwd;
    }
    if let Some(parent) = cwd.parent() {
        if parent.join("backend").join("app").join("main.py").exists() {
            return parent.to_path_buf();
        }
    }
    cwd
}

fn get_configured_hotkey() -> String {
    let root = get_workspace_root();
    let config_path = root.join("storage").join("shell_config.json");
    if let Ok(contents) = std::fs::read_to_string(config_path) {
        if let Ok(val) = serde_json::from_str::<serde_json::Value>(&contents) {
            if let Some(h) = val.get("hotkey").and_then(|v| v.as_str()) {
                let trimmed = h.trim();
                if !trimmed.is_empty() {
                    return trimmed.to_string();
                }
            }
        }
    }
    "Ctrl+Space".to_string()
}

fn ensure_backend_running() {
    // Check if port 8000 is open
    if std::net::TcpStream::connect("127.0.0.1:8000").is_ok() {
        log::info!("Backend is already running on 127.0.0.1:8000");
        return;
    }

    log::info!("Spawning local NIKO backend on 127.0.0.1:8000...");
    let root = get_workspace_root();
    let child_res = Command::new("uv")
        .current_dir(&root)
        .args([
            "run",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ])
        .spawn();

    match child_res {
        Ok(child) => {
            if let Ok(mut lock) = BACKEND_CHILD.lock() {
                *lock = Some(child);
                IS_BACKEND_SPAWNED.store(true, Ordering::SeqCst);
                log::info!("NIKO backend process spawned successfully.");
            }
        }
        Err(e) => {
            log::warn!("Could not automatically spawn backend via uv: {}. Assuming external process.", e);
        }
    }
}

fn stop_backend() {
    if IS_BACKEND_SPAWNED.load(Ordering::SeqCst) {
        if let Ok(mut lock) = BACKEND_CHILD.lock() {
            if let Some(mut child) = lock.take() {
                log::info!("Stopping NIKO backend child process...");
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    ensure_backend_running();

    tauri::Builder::default()
        .plugin(tauri_plugin_log::Builder::default().build())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(win) = app.get_webview_window("overlay") {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }))
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .setup(|app| {
            let hotkey = get_configured_hotkey();

            // Apply Windows 11 Acrylic / Mica if available
            if let Some(window) = app.get_webview_window("overlay") {
                #[cfg(target_os = "windows")]
                {
                    use window_vibrancy::{apply_acrylic, apply_mica};
                    // Try Mica first (Windows 11 22H2+), fall back to Acrylic
                    if apply_mica(&window, None).is_err() {
                        let _ = apply_acrylic(&window, Some((20, 20, 20, 180)));
                    }
                }
            }

            // Create System Tray Menu with configured hotkey in label
            let open_label = format!("Open Overlay ({})", hotkey);
            let open_item = MenuItem::with_id(app, "open", &open_label, true, None::<&str>)?;
            let dashboard_item = MenuItem::with_id(app, "dashboard", "Dashboard Window", true, None::<&str>)?;
            let settings_item = MenuItem::with_id(app, "settings", "Settings", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit NIKO", true, None::<&str>)?;

            let tray_menu = Menu::with_items(app, &[&open_item, &dashboard_item, &settings_item, &quit_item])?;

            let tray = TrayIconBuilder::new()
                .menu(&tray_menu)
                .show_menu_on_left_click(true)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "open" => {
                        if let Some(win) = app.get_webview_window("overlay") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "dashboard" => {
                        if let Some(win) = app.get_webview_window("overlay") {
                            let _ = win.show();
                            let _ = win.set_focus();
                            let _ = win.eval("window.location.search = '?view=dashboard';");
                        }
                    }
                    "settings" => {
                        if let Some(win) = app.get_webview_window("overlay") {
                            let _ = win.show();
                            let _ = win.set_focus();
                            let _ = win.eval("window.location.search = '?view=dashboard#settings';");
                        }
                    }
                    "quit" => {
                        stop_backend();
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            // Register global shortcut to toggle overlay visibility
            let hotkey_str = hotkey.clone();
            let reg_res = app.global_shortcut().on_shortcut(hotkey_str.as_str(), move |app, _shortcut, event| {
                if event.state == ShortcutState::Pressed {
                    if let Some(win) = app.get_webview_window("overlay") {
                        if win.is_visible().unwrap_or(false) {
                            let _ = win.hide();
                        } else {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                }
            });

            match reg_res {
                Ok(_) => {
                    log::info!("Registered global shortcut '{}' successfully", hotkey);
                    let _ = tray.set_tooltip(Some("NIKO - Personal AI Assistant"));
                }
                Err(e) => {
                    log::warn!(
                        "Global shortcut registration failed for '{}': {}. Key may be in use by another application.",
                        hotkey,
                        e
                    );
                    let conflict_msg = format!("NIKO - Hotkey conflict ('{}' in use)", hotkey);
                    let _ = tray.set_tooltip(Some(&conflict_msg));
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|_app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                stop_backend();
            }
        });
}

