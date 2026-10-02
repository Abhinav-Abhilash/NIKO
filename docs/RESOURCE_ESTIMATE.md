# NIKO Resource Estimation & Capacity Planning
**Date:** September 2026  
**Profile:** Single-Owner Localhost Assistant (Zero Local Models, Pure API Fallback Chain: Gemini $\to$ Groq $\to$ OpenRouter)

---

## 1. Storage Footprint & Growth Projections

### A. Fresh Installation Footprint
| Component | Disk Size | Notes |
| :--- | :--- | :--- |
| **Python Virtual Environment (`.venv`)** | ~165 MB | Fast, pure-Python wheels via `uv` (FastAPI, SQLAlchemy, Cryptography, Pydantic, Structlog). With OS extras (`psutil`, `mss`, `Pillow`, `pycaw`), total is ~210 MB. |
| **Node.js (`node_modules`)** | ~190 MB | Vite, React 18, TanStack Query/Router, Zustand, Tailwind, Lucide, Framer Motion, cmdk. |
| **Built Frontend Bundle (`dist/`)** | ~6 MB | Optimized, minified, gzipped static production assets. |
| **Source Code & Git Metadata** | ~15 MB | Repository files, schemas, and git history. |
| **Initial Fresh Total** | **~420 MB - 475 MB** | **Well within the < 1 GB budget; zero Docker, zero torch.** |

---

### B. SQLite Database Growth & 500 MB Alert Horizon
**Assumptions for Active Daily Use:**
- **Chats:** 50 messages/day (~1,500 messages/month). Average message size ~1.5 KB $\implies$ **~2.25 MB/month**.
- **Tool Calls:** 30 tool executions/day (~900/month). Average JSON args/results ~2 KB $\implies$ **~1.8 MB/month**.
- **Command Logs & Approvals (90-day retention):** 30 records/day. Caps at ~2,700 rows $\implies$ **~4.0 MB stable footprint**.
- **System Metrics (30-day retention):** Downsampled to 1-minute aggregates ($60 \times 24 \times 30 = 43,200$ rows). Each row is 4 floats + timestamp + PK $\approx$ 120 bytes (including B-tree indices) $\implies$ **~5.2 MB stable cap**.
- **Net DB Growth:** **~4.05 MB per month** (metrics and command logs are capped by retention; only conversation text grows).

> [!NOTE]
> **When does SQLite hit the 500 MB Warning Threshold?**  
> - Under **typical daily use** (50 messages/day): $(500\text{ MB} - 10\text{ MB base}) / 4.05\text{ MB/mo} \approx$ **121 months (~10 years)**.  
> - Under **heavy daily use** (250 messages/day, ~20 MB/mo): $\approx$ **24.5 months (~2 years)**.  
> SQLite will remain exceptionally lean without manual database pruning.

---

### C. Screenshots (WebP) with 7-Day Retention
- **Format:** WebP lossless/lossy (Quality: 80).
- **Size per capture:**
  - 1080p display: **120 KB – 220 KB** (avg ~170 KB).
  - 1440p / 4K display: **320 KB – 500 KB** (avg ~380 KB).
- **Active storage with 7-day retention:**
  - *Typical use (5 screenshots/day):* 35 captures $\times$ 180 KB = **~6.3 MB**.
  - *Heavy / automated monitoring (100 screenshots/day):* 700 captures $\times$ 350 KB = **~245 MB**.

---

### D. Structured Logs after Rotation
- **Rotation policy:** 10 MB maximum file size, 5 backup archives retained.
- **Maximum log footprint:** Strictly capped at **50 MB** (`storage/logs/niko.log` + 5 archives).

---

### E. Total Storage Summary after 1 Year
| Scenario | Install | SQLite DB (1 yr) | Screenshots (7-day cap) | Logs (Cap) | Total Footprint |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Minimum** (Light chat, few tools) | 420 MB | ~20 MB | ~2 MB | ~10 MB | **~452 MB** |
| **Typical** (50 msgs/day, regular use) | 450 MB | ~55 MB | ~8 MB | ~30 MB | **~543 MB** |
| **Worst-Case** (250 msgs/day, heavy screen) | 475 MB | ~250 MB | ~250 MB | ~50 MB | **~1.025 GB** |

---

## 2. Compute, Memory & Network Profile

### A. RAM Consumption
| Component | Idle | Peak / Active |
| :--- | :--- | :--- |
| **Backend (FastAPI, SQLite, APScheduler)** | **55 MB – 65 MB** | **85 MB – 110 MB** (during JSON deserialization, Fernet decryption, and in-memory WebP image compression) |
| **Frontend (Single Chromium Tab / Webview)** | **85 MB – 110 MB** | **120 MB – 160 MB** (rendering real-time uPlot graphs, streaming markdown, and animated state orb) |
| **Total System RAM** | **~140 MB – 175 MB** | **~205 MB – 270 MB** |

---

### B. CPU Utilization
| Operation | Typical CPU Load | Duration / Frequency |
| :--- | :--- | :--- |
| **System Idle** | **< 0.2%** of 1 core | Continuous (event loop waiting on I/O) |
| **2-Second System Metrics Loop** | **~1.0% – 1.8%** of 1 core | 5 milliseconds every 2 seconds |
| **Streaming Chat Handling** | **~1.5% – 3.0%** of 1 core | Active only during LLM token streaming |
| **Screenshot & WebP Compression** | **15% – 25%** of 1 core | Short burst: 35 – 70 milliseconds per shot |
| **Average Sustained CPU** | **< 0.5%** | Negligible thermal or battery impact |

---

### C. Network Bandwidth (WebSocket & HTTP)
- **Localhost WebSocket Metrics Traffic:**
  - Metrics packet: ~180 bytes every 2 seconds = 90 bytes/sec $\implies$ **~324 KB per hour**.
- **Streaming Chat:**
  - Average 500-token response: ~2.5 KB total transferred over ~4 seconds.
  - 20 turns/hour = **~50 KB per hour**.
- **External Internet Bandwidth:**
  - Exclusively outgoing HTTPS calls to Gemini / Groq / OpenRouter APIs (~2 KB – 5 KB per turn). Zero bandwidth consumed by background metrics (metrics stay 100% on localhost).

---

## 3. LLM Quota Capacity & Optimization

### A. Token Usage per Turn (with Optimization & Pruning)
- **Standard Chat Turn:**
  - Prompt + Sliding Context (last 6 messages): **~450 – 800 input tokens**.
  - Generated Response: **~150 – 400 output tokens**.
- **Tool-Calling Turn:**
  - System Prompt + MCP Tool Schemas + Context: **~850 – 1,600 input tokens**.
  - Generated Tool Call Arguments: **~60 – 150 output tokens**.
  - Tool Result Re-injection (Pruned): **~300 – 600 input tokens**.

---

### B. Daily Free-Tier Capacity Before Chain Exhaustion
| Provider | Free Tier Allotment | Daily Capacity in NIKO Turns |
| :--- | :--- | :--- |
| **1. Google Gemini Flash-Lite (Primary)** | 15 RPM / 500 RPD / 250K TPM | **~500 turns / day** |
| **2. Google Gemini Flash Ladder (Hard Tasks)** | 5 RPM / 20 RPD (3.8, 3.7, 3.5 pools) | **~60 turns / day total (4 reserved/pool)** |
| **3. Groq (Fast / Short Code)** | 30 RPM / 1,000 RPD / 8K TPM | **~1,000 turns / day** |
| **4. OpenRouter (Tertiary Standby)** | 20 RPM / 200 RPD | **~200 turns / day** |
| **Combined Chain Capacity** | **~1,700+ turns per day completely free** | Source: AI Studio rate-limit page, read by owner, 2026-10-02 |

---

### C. Recommended Exhaustion Policy: "Graceful Cooldown Banner + Deferred Queue"
When all three providers hit rate limits (HTTP 429 / quota exceeded):
1. **Immediate Non-Blocking Banner:**  
   The UI immediately presents a clean notification:  
   *"All free LLM quotas are temporarily cooling down. Shortest reset: Groq in 4 minutes, 20 seconds."*
2. **Deferred Request Queue (One-Click):**  
   The user's prompt is saved to an in-memory queue. As soon as the cooldown timer expires, NIKO automatically dispatches the prompt, plays a subtle notification tone, and delivers the response.

---

## 4. Hosting Suitability: Cloud vs. Localhost

### A. Running on a 512 MB Free Cloud Container (e.g., Render, Railway, Fly.io)
**Can it run?**  
Yes, the backend consumes only ~65 MB idle and ~100 MB under load, fitting easily within 512 MB RAM.

**What must change if hosted in the Cloud:**
1. **Local System Skills:**
   - Skills like `open_app`, `volume_brightness`, `screenshot`, and `psutil` would observe the *cloud container*, not the user's laptop.
   - *Fix:* Must implement a lightweight local agent (`RemoteAgentExecutor`) on the user's PC communicating back to the cloud via WebSocket.
2. **Database:**
   - SQLite requires persistent block storage volumes. Migrating to a managed serverless PostgreSQL (e.g. Supabase free tier) eliminates volume locking and allows seamless horizontal restarts.
3. **Loopback & WebSocket Security:**
   - `127.0.0.1` binding and local Origin checks must be updated to authenticate via JWT headers over public WSS.

---

### B. Minimum Hardware Recommendations
| Environment | Minimum Recommended Specs |
| :--- | :--- |
| **Local PC (Windows / Mac / Linux)** | 2 CPU Cores, 256 MB free RAM, 1 GB free disk space. |
| **Cloud Container (Remote Headless)** | 1 vCPU, 512 MB RAM, 1 GB persistent disk. |

---

## 5. Top 3 Storage / Compute Risks & Cheap Fixes

### Risk 1: Unthrottled WebSocket Metrics Flooding
- **Symptom:** Broadcasting CPU/RAM metrics every 2 seconds when the browser window is minimized or the user is away wastes background CPU and battery.
- **Cheap Fix:** **Window Focus / Tab Visibility Throttling**. The frontend emits `tab:visibility` changes; when the tab is hidden, the backend drops metric collection frequency from 2s to 15s. *(User toggleable in Settings).*

### Risk 2: Unbounded Tool Output Blowing Prompt Budgets
- **Symptom:** A web search or file read returning a massive 50 KB raw payload consumes thousands of prompt tokens in one turn, depleting free quotas prematurely.
- **Cheap Fix:** **Adaptive Head-Tail Pruning Guard**. Before re-injecting tool output into the LLM context, truncate output to a maximum of 1,200 tokens (preserving the first 600 and last 600 tokens with an ellipsis). The complete output remains safely stored in the database `tool_calls.result_json` for user review.

### Risk 3: Screenshot Disk Accumulation in Burst Workflows
- **Symptom:** If the user takes frequent manual captures or uses screen analysis heavily, 7 days of 4K screenshots can consume gigabytes.
- **Cheap Fix:** **Storage Quota Hard-Cap with FIFO Pruning**. Add a `MAX_SCREENSHOT_STORAGE_MB` setting (default: 250 MB). When the folder exceeds 250 MB, the oldest screenshots are automatically pruned, regardless of whether 7 days have passed.

---

## 6. Spec Changes Needed to Remove Ollama *(Reference List Only - Not Yet Applied)*

To cleanly eliminate local model references and Ollama from the architecture:
1. **`/docs/ARCHITECTURE.md`**:
   - Remove `[4. Local Ollama (Offline)]` from the Fallback Chain diagram.
   - Remove "Offline / Local Ollama" references from Section 2, Section 4, and Section 9.
2. **`backend/app/db/models/__init__.py`**:
   - Update `LLMProviderModel` comments to list `(gemini, groq, openrouter)` only.
3. **`backend/app/api/v1/auth.py`**:
   - Remove the `{"name": "ollama", ...}` dict from the `provider_seeds` list during initial setup.
4. **`backend/app/llm/`**:
   - Skip implementing `backend/app/llm/ollama.py` in Milestone 4.
