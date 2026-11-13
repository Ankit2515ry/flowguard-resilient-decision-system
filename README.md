# FlowGuard

FlowGuard is a configurable workflow decision platform. This repository currently contains
the Phase 1 scaffold: a FastAPI application with a health check, package structure,
architecture documents and a smoke test. Workflow rules, persistence and decision APIs are
planned work and are not implemented yet.

## Requirements

- Python 3.11 or newer
- pip

## Install

From the repository root, create and activate a virtual environment, then install the project
and development dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run

```powershell
python -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger UI. Health check: `http://127.0.0.1:8000/health`.

## Test

```powershell
python -m pytest -q
```

## Project map

- `app/`: modular application package
- `configs/workflows/`: workflow configuration examples (to be added in Phase 2)
- `tests/`: unit, integration and failure test suites
- `docs/`: architecture and design contracts
- `project_management/`: phase plan, tasks, decisions, evidence and handoff

See `project_management/HANDOFF.md` for the exact next task. Only Phase 1 is implemented.
