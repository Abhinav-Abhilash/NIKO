import subprocess
import time
import json
import os
import signal

def get_current_processes():
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-Process | Select-Object Id, ProcessName, WorkingSet64, CPU | ConvertTo-Json"
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        data = json.loads(res.stdout)
        if isinstance(data, dict):
            data = [data]
        return {p["Id"]: p for p in data if "Id" in p}
    except Exception as e:
        print("Failed to parse processes:", e)
        return {}

def main():
    print("Capturing baseline processes before launch...")
    baseline = get_current_processes()
    baseline_pids = set(baseline.keys())

    print("Spawning 'npm run desktop'...")
    proc = subprocess.Popen(
        ["npm.cmd", "run", "desktop"],
        cwd=r"e:\NIKO AI",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print("Waiting 12 seconds for Tauri window, WebView2 runtime, Vite server, and Python backend to settle...")
    time.sleep(12)

    current = get_current_processes()
    new_pids = set(current.keys()) - baseline_pids

    # Categorize new processes
    records = []
    for pid in new_pids:
        p = current[pid]
        pname = p.get("ProcessName", "").lower()
        ws_mb = (p.get("WorkingSet64") or 0) / (1024 * 1024)
        cpu = p.get("CPU") or 0.0
        records.append({
            "pid": pid,
            "name": p.get("ProcessName"),
            "ram_mb": ws_mb,
            "cpu": cpu
        })

    # Sample again 3 seconds later to measure active CPU delta
    time.sleep(3)
    sample2 = get_current_processes()
    for r in records:
        pid = r["pid"]
        if pid in sample2:
            cpu2 = sample2[pid].get("CPU") or 0.0
            ws2_mb = (sample2[pid].get("WorkingSet64") or 0) / (1024 * 1024)
            # CPU% over 3 seconds = (cpu2 - cpu) / 3 * 100
            cpu_pct = max(0.0, (cpu2 - r["cpu"]) / 3.0 * 100.0)
            r["cpu_pct"] = round(cpu_pct, 2)
            r["ram_mb"] = round(ws2_mb, 2)
        else:
            r["cpu_pct"] = 0.0

    print("\n--- REAL BENCHMARK RESULTS FOR 'npm run desktop' ---\n")
    print(f"{'Process Name':<25} {'PID':<8} {'RAM (MB)':<12} {'CPU (%)':<10}")
    print("-" * 58)

    total_ram = 0.0
    total_cpu = 0.0

    # Group into categories
    tauri_ram = 0.0
    webview_ram = 0.0
    backend_ram = 0.0
    vite_ram = 0.0

    for r in sorted(records, key=lambda x: x["ram_mb"], reverse=True):
        print(f"{r['name']:<25} {r['pid']:<8} {r['ram_mb']:<12.1f} {r['cpu_pct']:<10.1f}")
        total_ram += r["ram_mb"]
        total_cpu += r["cpu_pct"]

        n = r["name"].lower()
        if "app" in n:
            tauri_ram += r["ram_mb"]
        elif "msedgewebview2" in n:
            webview_ram += r["ram_mb"]
        elif "python" in n or "uv" in n:
            backend_ram += r["ram_mb"]
        elif "node" in n:
            vite_ram += r["ram_mb"]

    print("-" * 58)
    print(f"{'TOTAL FOOTPRINT':<25} {'':<8} {total_ram:<12.1f} {total_cpu:<10.1f}%\n")

    print(f"Summary Breakdown:")
    print(f"  • Tauri Rust Shell (app.exe):                  {tauri_ram:.1f} MB")
    print(f"  • Edge WebView2 Runtime (Pet Window):          {webview_ram:.1f} MB")
    print(f"  • Python Backend Service (Uvicorn / FastAPI):  {backend_ram:.1f} MB")
    print(f"  • Vite Frontend Dev Server (Node.js):          {vite_ram:.1f} MB")
    print(f"  -------------------------------------------------------------")
    print(f"  • Desktop Pet Client Alone (Rust + WebView2):  {tauri_ram + webview_ram:.1f} MB")
    print(f"  • Complete Stack (Client + Backend + Vite):    {total_ram:.1f} MB")

    # Clean termination
    print("\nTerminating test desktop instance...")
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Also ensure app.exe is closed
    subprocess.run(["taskkill", "/F", "/IM", "app.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Benchmark complete.")

if __name__ == "__main__":
    main()
