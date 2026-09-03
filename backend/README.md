# SIH26182 — Backend (Person B / Branch B: feature/investigator-platform)

FastAPI + SQLite backend for the wallet attribution investigator platform.

## Setup
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API docs (auto-generated): http://localhost:8000/docs

## Endpoints
- `POST /api/trace` — `{"address": "...", "max_hops": 5}` → runs the tracing
  engine (currently `sample_engine.py`, a stand-in — see below), computes
  risk flags, saves the case, returns the full `CaseDetail`.
- `GET /api/cases` — list all past cases (summary view).
- `GET /api/cases/{id}` — full case detail including the trace.
- `GET /api/cases/{id}/report` — downloads a PDF investigation report.

## Files
| File | Purpose |
|---|---|
| `app/schemas.py` | Pydantic models matching the Section 3 JSON contract exactly |
| `app/models.py` | SQLAlchemy `Case` table |
| `app/database.py` | SQLite engine/session setup |
| `app/risk_engine.py` | Risk-flag rules (rapid_hopping, high_fanout, possible_mixer) — **your logic**, computed from hops |
| `app/sample_engine.py` | **Stand-in for Person A's tracing engine.** Deterministic fake trace data so you can build/test everything now. |
| `app/report_generator.py` | PDF report builder (reportlab) |
| `app/main.py` | FastAPI routes |

## Swapping in Person A's real engine — DONE
`sample_engine.py`'s `trace_address()` now calls Person A's real
`tracing_engine.engine.trace_wallet` internally. `main.py` still imports
`trace_address` from `.sample_engine` unchanged -- the local name was kept
stable on purpose so nothing else in this backend needed to change at
swap time. (Note: `tracing_engine` only exports `trace_wallet`, not
`trace_address` -- importing `trace_address` directly from `tracing_engine`,
as an earlier draft of this README suggested, would fail.)

## Not yet built (next steps for Branch B)
- Interactive graph visualization (Cytoscape.js) consuming `GET /api/cases/{id}` hops data
- Case-list dashboard UI
- Edge-case handling (unresolved addresses, API timeouts once real engine is plugged in)
