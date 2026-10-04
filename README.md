# Group Project Referee

**A local-AI assistant for understanding the real state of collaborative projects.**

Built for the [Hacktoberfest Weekend Challenge: Build for a Friend](https://dev.to/challenges/hacktoberfest-weekend-2026-10-01).

**Repository:** https://github.com/Gitcarbonath/group-project-referee

## Why I built it

Group projects are difficult to coordinate when updates arrive as informal messages. One teammate may finish an API while another still cannot access it; a blocker may be resolved without everyone noticing. Group Project Referee was built to help teammates see progress, dependencies, risks, and unresolved work without assigning blame.

## What it does

Teammates submit natural-language updates, such as:

> I am working on the authentication tests. I need the database migration before I can run them.

The application stores the updates and uses **Gemma 3 running locally through Ollama** to interpret project events. A project dashboard displays:

- Completed, in-progress, and blocked work
- Risks and possible conflicts
- Dependencies and suggested next actions
- A chronological update timeline
- Evidence linking findings to the original team updates
- Multiple projects and team members

The referee is an aid to discussion, **not an authority on which teammate is right**. Its findings should be verified against the linked updates.

## Architecture

```text
Team members (browser)
        |
        v
React + Vite frontend
        |
        v
FastAPI backend --------> SQLite (projects, members, updates)
        |
        v
Ollama (local inference)
        |
        v
Gemma 3 (event extraction)
        |
        v
Project-state processing
        |
        v
Dashboard and evidence trail
```

The application separates the historical timeline from the current project summary. For example, an earlier access problem can remain visible in the timeline even after a later update reports that it was fixed. Local inference may take time; the interface can display submitted updates while analysis is pending.

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI |
| Storage | SQLite |
| Local AI | Gemma 3 (`gemma3:4b`) via Ollama |

## Run locally

### Prerequisites

- Python 3.10+ (the project was developed with Python 3.14)
- Node.js and npm
- [Ollama](https://ollama.com/)
- Git
- Enough available RAM to run the selected Gemma model

### 1. Clone

```bash
git clone https://github.com/Gitcarbonath/group-project-referee.git
cd group-project-referee
```

### 2. Prepare the local model

Install Ollama, then run:

```bash
ollama pull gemma3:4b
```

Make sure Ollama is running locally before requesting AI analysis.

### 3. Start the backend

**Windows PowerShell:**

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install fastapi uvicorn pydantic requests
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If PowerShell prevents activation, you can invoke `.venv\Scripts\python.exe` and `.venv\Scripts\uvicorn.exe` directly instead.

Backend API documentation: http://localhost:8000/docs

> **Database setup:** The backend uses a local SQLite database. No existing project data is included in this repository. If the application does not initialize its tables at startup, check the backend initialization instructions in `main.py` / `database.py` before submitting updates.

### 4. Start the frontend

Open a **second terminal** at the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the local address printed by Vite (normally http://localhost:5173).

### 5. Try it

1. Create or select a project.
2. Add team members.
3. Submit updates in everyday language.
4. Review the dashboard, timeline, and evidence links.
5. Submit a later update resolving a previously reported problem and compare the history with the current summary.

### Optional: access from another device on the same network

The development setup can be exposed on a trusted local network by starting Vite with `npm run dev -- --host 0.0.0.0` and opening `http://YOUR_PC_IP:5173` on another device. The backend must also be reachable on port 8000. Network firewall rules and the frontend API host configuration may need adjustment. **This is a development/LAN setup, not a production-secured deployment; do not expose it directly to the public internet.**

## Demo

https://drive.google.com/file/d/1UFVnYGsj6oXr8sYMaWgfnMKzoPrJS7zS/view?usp=sharing

## Open innovation

Gemma 3 is an open-weight model that can run locally. For this project, local inference helps keep internal team updates on the host machine and allows experimentation with prompts and event extraction without requiring a paid hosted-model API. Open tools such as Ollama, FastAPI, React, and SQLite also make the application easier to study and extend.

## Current limitations

- AI-generated classifications can be incomplete or incorrect, particularly when updates are ambiguous.
- Model inference speed depends on the host hardware; analysis may be delayed.
- The project is a local prototype, not a hardened public multi-tenant service.
- Team statements are evidence of *reported* progress, not independent verification that code was merged or tested.

## Possible next steps

- GitHub issue/commit corroboration
- Stronger task identity and resolution tracking
- More reliable conflict and risk deduplication
- Authentication and production-ready deployment
- Automated tests and evaluation cases for extraction accuracy

## Credits

Created for the **Build for a Friend** challenge to help teammates coordinate group work.
