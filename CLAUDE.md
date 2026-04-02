# A.D.A V2 — AI Desktop Assistant

## Project Overview

A.D.A (Advanced Desktop Assistant) is an Electron + React + Python desktop app. It uses Google Gemini's multimodal live API for conversational AI, with agents for CAD generation, 3D printing, smart home control, web browsing, and face authentication.

## Architecture

```
electron/main.js        — Electron host, spawns Python backend, manages window
src/                    — React frontend (Vite + Tailwind CSS)
  App.jsx               — Main app shell, socket.io connection, MediaPipe setup
  components/           — UI modules (Chat, CAD, Printer, Kasa, Browser, Auth, Settings)
backend/                — Python backend (FastAPI + Socket.IO)
  server.py             — FastAPI server on port 8000, Socket.IO event handlers
  ada.py                — Core Gemini live session (AudioLoop), tool dispatch
  cad_agent.py          — Generates & iterates CAD models via build123d
  printer_agent.py      — 3D printer control (OctoPrint/Moonraker)
  kasa_agent.py         — Kasa smart home device control
  web_agent.py          — Headless browser automation via Playwright
  authenticator.py      — Face authentication via MediaPipe
  project_manager.py    — File/project management
  tools.py              — Tool schema definitions for Gemini function calling
  settings.json         — Runtime config (printers, devices, permissions)
tests/                  — Pytest test suite
```

## Tech Stack

- **Frontend:** React 18, Vite, Tailwind CSS, Three.js (STL viewer), Framer Motion, Socket.IO client
- **Backend:** Python, FastAPI, Socket.IO (async), Google GenAI SDK
- **Desktop:** Electron 28
- **AI:** Google Gemini Live API (multimodal — audio, video, screen share)
- **Agents:** build123d (CAD), Playwright (web), python-kasa (smart home), OctoPrint/Moonraker (3D printing), MediaPipe (face/hand tracking)

## Commands

### Run (development)
```bash
# Terminal 1 — backend
cd backend && python server.py

# Terminal 2 — frontend + Electron
npm run dev
```

Or just `npm run dev` which uses concurrently to run Vite and Electron together (backend must be started separately or Electron auto-starts it).

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
```

## Key Conventions

- Frontend communicates with backend exclusively via Socket.IO (port 8000)
- Backend agents are instantiated in `server.py` and invoked through Gemini tool calls defined in `tools.py`
- Settings are persisted in `backend/settings.json` and synced to frontend via socket events
- Binary data (audio, images, STL files) is base64-encoded for socket transport
- The app runs on Windows (asyncio WindowsProactorEventLoopPolicy is set in server.py)

## Docker (Unraid deployment)

Multi-stage build: Node builds frontend, Python serves everything.

```bash
# Build locally
docker build -t ada-v2 .

# Run via compose (set GEMINI_API_KEY in .env or environment)
docker compose up -d
```

- GitHub Action (`.github/workflows/docker-publish.yml`) auto-builds and pushes to `ghcr.io/etlon/ada_v2` on push to main
- `docker-compose.yml` is configured for Unraid paths (`/mnt/user/appdata/ada-v2/`)
- Settings and projects are persisted via volume mounts

## Ports

- `5173` — Vite dev server (frontend, dev only)
- `8000` — FastAPI/Socket.IO (backend, also serves frontend in Docker)
