# Third-Party Notices & Licensing Disclosures

This document catalogues third-party projects, code references, design inspirations, and license notices relevant to the NIKO virtual companion desktop client.

---

## 1. Open-LLM-VTuber-Web

- **Repository**: [Open-LLM-VTuber/Open-LLM-VTuber-Web](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber-Web)
- **Author / Copyright**: Copyright © 2025 Open LLM Vtuber. All rights reserved.
- **License**: Open-LLM-VTuber License 1.0 (Apache License 2.0 with Additional Commercial Restrictions)
- **Inspection Commit**: `d176e7df2366952e3bacbf12cf9a8b18a4315932`
- **Usage in NIKO**: Architectural inspection and research reference only. NIKO does **not** bundle or vendor Open-LLM-VTuber source files or dependencies.
- **Key License Terms**:
  - *Permitted Uses*: Non-commercial activities including personal projects, education, academic research, non-profit initiatives, and content creation/streaming where revenue is derived from content rather than direct sale of software.
  - *Restricted Uses*: Commercial distribution, rebranded redistribution, paid hosting/SaaS access, or commercial embedding require an explicit separate commercial license from Open LLM Vtuber.

---

## 2. Mark-LV (Live2D & Motion Models)

- **Author**: Mark-LV
- **License**: Creative Commons Attribution-NonCommercial 4.0 International ([CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/))
- **Usage & Boundary**:
  - NIKO **does NOT** copy, redistribute, or package any sample Live2D models or assets from Mark-LV.
  - Any architectural adaptations inspired by Mark-LV's motion/interaction patterns remain non-commercial and credited here in accordance with CC BY-NC 4.0.

---

## 3. Live2D Cubism SDK Notice

- **Proprietary Notice**: The Live2D Cubism SDK Core and sample frameworks are proprietary intellectual property of **Live2D Inc.**
- **Policy**: NIKO does **not** include, bundle, or distribute Live2D Cubism Core binaries (`live2d.min.js`, `live2dcubismcore.min.js`) or proprietary sample models. NIKO's desktop pet runtime uses lightweight procedural sprites and SVG rendering.

---

## 4. Native Desktop Shell & Core Dependencies

| Component | Upstream Project | License | Purpose in NIKO |
|---|---|---|---|
| **Tauri v2** | [Tauri Apps](https://github.com/tauri-apps/tauri) | Apache-2.0 / MIT | Borderless transparent desktop pet window and OS shell |
| **Microsoft Edge WebView2** | Microsoft Corporation | Redistributable Runtime License | System webview rendering engine on Windows |
| **React 19** | Meta Platforms, Inc. | MIT | Declarative UI components and state management |
| **Vite** | VoidZero / Evan You | MIT | Fast frontend development server and bundler |
