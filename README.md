# 🧞 Jin

**Jin** is a personal, agentic voice system — a programmable _genie_ for your digital life.

Wake it with **“Hey Jin”**, ask questions, trigger workflows, approve actions, and let it execute tasks across your apps and systems — transparently and safely.

Jin is built as a **learning-first, open‑source project** that combines:

- Hardware (Raspberry Pi)
- Agentic AI (LangChain)
- Backend systems (Django + Celery)
- Frontend dashboards (Next.js)

---

## ✨ Core Principles

- **Agentic, not magical** – every action is observable, logged, and explainable
- **Human‑in‑the‑loop by default** – intrusive actions require approval
- **Modular & provider‑agnostic** – swap LLMs, STT, TTS, music providers
- **Voice‑first, UI‑backed** – voice for intent, UI for trust & control
- **OSS‑friendly** – run hardware‑only, software‑only, or full stack

---

## 🔊 What Jin Can Do (Current & Planned)

### Voice & Interaction

- Wake word: **“Hey Jin”** (local on Raspberry Pi)
- Low‑latency speech‑to‑text (Deepgram)
- Natural text‑to‑speech responses

### Agentic Workflows

- Multi‑step task planning (LangChain)
- Tool‑calling with guardrails
- Human approval gates
- Task provenance & audit logs

### Integrations

- 📈 Finance (Angel One – read‑only portfolio insights)
- 📧 Google Workspace (Gmail, Docs, Calendar)
- 🎵 Music (Spotify Connect via Raspberry Pi)
- 🧠 Memory (vector store for long‑term context)

### Dashboard (Web UI)

- Task timeline & execution steps
- Approve / reject actions
- Integration management (connect / revoke accounts)
- Agent reasoning visibility (what ran, why)

---

## 🏗️ Architecture Overview

```
User (Voice / UI)
   ↓
Raspberry Pi (Wake word, audio capture)
   ↓
Backend (Django + DRF)
   ├─ Agent orchestration (LangChain)
   ├─ Task execution (Celery)
   ├─ Integrations (Spotify, Google, etc.)
   └─ Audit & memory
   ↓
Services (Deepgram, LLMs, APIs)
```

---

## 📁 Repository Structure (Monorepo)

```
jin/
├── backend/        # Django + DRF + Celery + agents
├── webui/          # Next.js + TypeScript dashboard
├── edge/           # Raspberry Pi client (audio, wake word)
├── infra/          # Docker, nginx, deployment scripts
├── docs/           # Architecture & contributor docs
└── README.md
```

Each folder is **independently runnable** and loosely coupled via APIs.

---

## 🧠 Tech Stack

### Backend

- **Django + Django REST Framework** – APIs, auth, admin
- **Celery + Redis** – async agent execution
- **LangChain** – agentic reasoning & tool orchestration

### Frontend

- **Next.js + TypeScript**
- **Tailwind / shadcn‑ui** (planned)

### Voice

- **Wake word**: local on Raspberry Pi
- **STT**: Deepgram (streaming)
- **TTS**: Deepgram (initially, pluggable)

### Hardware

- **Raspberry Pi 4**
- USB microphone
- Speaker via AUX (e.g. Bose SoundLink)

---

## 🎵 Music Playback (Spotify)

Jin supports music via **Spotify Connect**:

- Raspberry Pi runs a Spotify Connect client
- Jin controls playback via Spotify Web API
- Audio plays locally on the Pi

No raw audio streaming, no ToS issues.

---

## 🔐 Security & Safety

- No credentials stored on the Pi
- OAuth tokens stored server‑side only
- Fine‑grained scopes per integration
- Explicit approval required for sensitive actions
- Full audit trail of agent behavior

---

## 🚀 Getting Started (High‑Level)

> Detailed setup guides live in `docs/`

1. Clone the repo
2. Run backend (Django + Celery)
3. Run frontend (Next.js)
4. Set up Raspberry Pi client
5. Say **“Hey Jin”**

---

## 🧪 Project Status

Jin is **actively evolving** and optimized for:

- Learning
- Experimentation
- Personal use

Expect breaking changes early on.

---

## 🧩 Extending Jin

Jin is built to be extended:

- Add new **tools** (APIs, systems)
- Add new **providers** (music, STT, TTS)
- Add new **agents** (finance, research, ops)

No core refactors required.

---

## 🤝 Contributing

Contributions are welcome once the core stabilizes.

Guiding rules:

- Keep agents & tools framework‑agnostic
- No secrets in code
- Prefer clarity over cleverness

---

## 📜 License

MIT License

---

## 🧞 Why “Jin”?

_Jin_ (or _Jinn_) means **genie** in Hindi/Urdu/Arabic —

A being that listens, reasons, and acts — but only when asked.

> **Hey Jin.**
