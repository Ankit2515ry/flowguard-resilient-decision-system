# FlowGuard

FlowGuard is a configurable workflow decision platform. The current implementation includes
the Phase 1 FastAPI health endpoint and the Phase 2 versioned YAML configuration loader and
pure rule engine. Persistence, request intake, workflow execution, retries, audit storage,
review operations and decision APIs are later-phase work and are not implemented yet.

## Requirements

- Python 3.11 or newer
- pip

## Install

From the repository root in Windows PowerShell, create and activate a Python 3.11 virtual
environment, then install the project and development dependencies:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

If the Python launcher (`py`) is unavailable, use `python -m venv .venv` after confirming
`python --version` reports Python 3.11 or newer. You can run FlowGuard and its tests without
activating the environment by invoking `.venv\Scripts\python.exe` directly.

## Run

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for Swagger UI. Health check: `http://127.0.0.1:8000/health`.

## Test

```powershell
.venv\Scripts\python.exe -m pytest -q
```

## Project map

- `app/`: modular application package
- `configs/workflows/`: loan v1/v2 and vendor v1 YAML examples
- `tests/`: unit, integration and failure test suites
- `docs/`: architecture and design contracts
- `project_management/`: phase plan, tasks, decisions, evidence and handoff

Rule evaluation and loading can be used from `app.engine.config` and `app.engine.rules`.
`load_workflows()` validates all YAML files under `configs/workflows/`; `evaluate_rules()`
returns a deterministic outcome and trace. See `docs/LLD.md` for the schema and behavior.
See `project_management/HANDOFF.md` for the exact next task. Only Phases 1 and 2 are complete.
