use std::process::{Child, Command};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
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

#[tauri::command]
fn set_click_through(window: tauri::WebviewWindow, ignore: bool) -> Result<(), String> {
    window.set_ignore_cursor_events(ignore).map_err(|e| e.to_string())
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
        .invoke_handler(tauri::generate_handler![set_click_through])
        .setup(|app| {
            let hotkey = get_configured_hotkey();

            // Sized to the pet only, position at bottom right above taskbar
            if let Some(window) = app.get_webview_window("overlay") {
                if let Ok(Some(monitor)) = window.primary_monitor() {
                    let screen_size = monitor.size();
                    let scale_factor = monitor.scale_factor();
                    let win_w = (220.0 * scale_factor) as i32;
                    let win_h = (260.0 * scale_factor) as i32;
                    let margin_x = (32.0 * scale_factor) as i32;
                    let margin_y = (72.0 * scale_factor) as i32;
                    let pos_x = (screen_size.width as i32) - win_w - margin_x;
                    let pos_y = (screen_size.height as i32) - win_h - margin_y;
                    let _ = window.set_position(tauri::Position::Physical(tauri::PhysicalPosition::new(pos_x, pos_y)));
                }
            }

            // Create System Tray Menu with Show / Hide / Quit
            let show_item = MenuItem::with_id(app, "show", "Show Pet", true, None::<&str>)?;
            let hide_item = MenuItem::with_id(app, "hide", "Hide Pet", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit NIKO", true, None::<&str>)?;

            let tray_menu = Menu::with_items(app, &[&show_item, &hide_item, &quit_item])?;

            let tray = TrayIconBuilder::new()
                .menu(&tray_menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(win) = app.get_webview_window("overlay") {
                            let _ = win.show();
                            let _ = win.set_focus();
                        }
                    }
                    "hide" => {
                        if let Some(win) = app.get_webview_window("overlay") {
                            let _ = win.hide();
                        }
                    }
                    "quit" => {
                        stop_backend();
                        app.exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(win) = app.get_webview_window("overlay") {
                            if win.is_visible().unwrap_or(false) {
                                let _ = win.hide();
                            } else {
                                let _ = win.show();
                                let _ = win.set_focus();
                            }
                        }
                    }
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
                    let _ = tray.set_tooltip(Some("NIKO Desktop Pet"));
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
