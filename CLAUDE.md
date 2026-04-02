# A.D.A V2 — AI Desktop & Web Assistant

## Project Overview

A.D.A / JARVIS is a voice-driven AI assistant powered by Google Gemini's multimodal Live API. It runs as an Electron desktop app or as a Dockerized web app (deployed on Unraid). Features include CAD generation, 3D printing, smart home control (Kasa + Home Assistant), web browsing, face authentication, and timed reminders.

This is a fork of `nazirlouis/ada_v2`. The user's remote is `etlon/ada_v2`.

## Architecture

```
electron/main.js           — Electron host (desktop mode only)
src/                       — React frontend (Vite + Tailwind CSS)
  App.jsx                  — Main app, socket.io, browser audio I/O, MediaPipe
  components/              — UI modules (Chat, CAD, Printer, Kasa, Browser, Auth, Settings)
backend/                   — Python backend (FastAPI + Socket.IO)
  server.py                — FastAPI server, Socket.IO events, agent orchestration
  ada.py                   — Core Gemini live session (AudioLoop), tool dispatch
  cad_agent.py             — CAD generation & iteration via build123d
  printer_agent.py         — 3D printer control (OctoPrint/Moonraker)
  kasa_agent.py            — Kasa smart home device control
  homeassistant_agent.py   — Home Assistant REST API integration
  reminder_agent.py        — Timed reminders via asyncio
  web_agent.py             — Headless browser automation via Playwright
  authenticator.py         — Face authentication via MediaPipe
  project_manager.py       — File/project management
  tools.py                 — Tool schema definitions for Gemini function calling
  settings.json            — Runtime config (printers, devices, permissions, system prompt)
tests/                     — Pytest test suite
```

## Tech Stack

- **Frontend:** React 18, Vite, Tailwind CSS, Three.js (STL viewer), Framer Motion, Socket.IO client, Web Audio API
- **Backend:** Python, FastAPI, Socket.IO (async), Google GenAI SDK, aiohttp
- **Desktop:** Electron 28 (optional — app also runs as pure web app)
- **AI:** Google Gemini Live API (multimodal — audio, video, screen share)
- **Agents:** build123d (CAD), Playwright (web), python-kasa (smart home), Home Assistant REST API, OctoPrint/Moonraker (3D printing), MediaPipe (face/hand tracking), Frigate NVR (camera feeds), SymPy (math computation)

## Audio Architecture

Audio I/O runs in the **browser**, not on the server:
- **Mic capture:** Browser `getUserMedia` → resample to 16kHz mono PCM → `socket.emit('browser_audio')` → backend → Gemini
- **Playback:** Gemini → backend → `socket.emit('audio_data')` → browser Web Audio API (with GainNode for volume control)
- **Mute:** Stops sending audio chunks and freezes mic visualizer (via `isMutedRef`)

This enables headless Docker deployment — no pyaudio/sound card needed on the server.

## Gemini Tools

Tools are defined in `ada.py` and dispatched in `AudioLoop.receive_audio()`. Adding a new tool:
1. Define the tool schema dict in `ada.py` (before the `tools` list)
2. Add it to the `tools` list
3. Add the tool name to the `fc.name in [...]` check
4. Add the `elif fc.name == "your_tool":` handler
5. Add to `DEFAULT_SETTINGS["tool_permissions"]` in `server.py`

Current tools: `generate_cad`, `iterate_cad`, `run_web_agent`, `control_light`, `list_smart_devices`, `ha_list_entities`, `ha_control`, `ha_get_state`, `set_reminder`, `list_reminders`, `cancel_reminder`, `discover_printers`, `print_stl`, `get_print_status`, `show_camera`, `stop_camera`, `annotate_camera`, `calculate`, file/project management tools.

## Settings

Stored in `backend/settings.json`, editable from the Settings UI:
- **System prompt** — customizable personality (default: JARVIS). Apply triggers session restart.
- **Tool permissions** — per-tool confirmation toggle (`true` = requires confirmation, `false` = auto-execute)
- **Volume** — playback volume (0-100%), persisted in browser localStorage
- **Device selection** — mic, speaker, webcam
- **Printers/Kasa devices** — discovered and cached

## Commands

### Run (development)
```bash
# Terminal 1 — backend
cd backend && python server.py

# Terminal 2 — frontend + Electron
npm run dev
```

### Build
```bash
npm run build        # Vite production build
```

### Test
```bash
pytest               # Runs all tests in tests/
pytest tests/test_cad_agent.py  # Single test file
```
Pytest config is in `pytest.ini`. Uses `asyncio_mode = auto`.

### Install
```bash
npm install                     # Frontend dependencies
pip install -r requirements.txt # Python dependencies
playwright install              # Browser automation (if using web agent)
```

## Environment

Requires a `.env` file in project root (see `.env.example`):
```
GEMINI_API_KEY=your_key_here
HA_URL=http://192.168.2.x:8123
HA_TOKEN=your_long_lived_access_token
FRIGATE_URL=http://192.168.2.x:5001
```

## Docker (Unraid deployment)

Multi-stage Dockerfile: Node builds frontend, Python 3.11-slim serves everything.

```bash
docker compose up -d
```

- GitHub Action (`.github/workflows/docker-publish.yml`) auto-builds and pushes to `ghcr.io/etlon/ada_v2` on push to main
- `docker-compose.yml` configured for Unraid paths (`/mnt/user/appdata/ada-v2/`)
- Settings and projects persisted via volume mounts
- Accessed via HTTPS through Nginx Proxy Manager (e.g., `https://ada.server`)
- Requires HTTPS for browser mic access (`navigator.mediaDevices`)

### Compose environment variables
```
GEMINI_API_KEY, HA_URL, HA_TOKEN, FRIGATE_URL, HOST (default 0.0.0.0), PORT (default 8000)
```

## Key Conventions

- Frontend ↔ backend communication is exclusively via Socket.IO
- Backend agents are instantiated in `server.py` and invoked through Gemini tool calls
- Settings persisted in `backend/settings.json`, synced to frontend via socket events
- Binary data (audio, images, STL) is base64-encoded for socket transport
- Electron imports are optional — app works in browser-only mode for Docker
- `server.py` serves built frontend from `dist/` when present (production/Docker)
- System prompt is configurable at runtime from the Settings UI

## Ports

- `5173` — Vite dev server (frontend, dev only)
- `8000` — FastAPI/Socket.IO (backend, default; configurable via PORT env var)
