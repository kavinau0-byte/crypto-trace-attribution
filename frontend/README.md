# Investigator Dashboard (frontend)

React dashboard for the SIH26182 wallet-attribution prototype. Submit a Bitcoin
address, watch the trace run, and review the attribution result and the fund-flow
graph it produced.

Built with React 18 + Vite, Tailwind CSS, react-router-dom, and
`react-force-graph-3d` for the transaction-flow visualization.

## Running it

The dashboard is a client for the FastAPI backend in `../backend`, so start the
backend first.

**1. Backend** — from the repository root:

```bash
cd backend
uvicorn app.main:app --reload
```

The backend imports `tracing_engine` from the repository root, so run it with the
repo root importable. If `uvicorn` reports `ModuleNotFoundError: No module named
'tracing_engine'`, launch it as:

```bash
PYTHONPATH="$(cd .. && pwd)" uvicorn app.main:app --reload
```

**2. Frontend** — in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite prints a local URL (`http://localhost:5173` by default). Open it in a browser.

Other scripts:

```bash
npm run build     # production build into dist/
npm run preview   # serve the production build locally
```

### A note on hot reload

This repository lives on a Windows drive (`/mnt/c/...`). Running the dev server
from WSL there means file-change events never reach Vite, so edits silently fail
to hot-reload until you restart. `vite.config.js` therefore enables a polling
watcher by default. On a native Linux or macOS filesystem the default watcher is
cheaper and sufficient — turn polling off with:

```bash
VITE_NO_POLLING=1 npm run dev
```

## Configuration

The API base URL is the only setting.

| Variable | Default | Purpose |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://localhost:8000` | Base URL of the FastAPI backend |

Copy `.env.example` to `.env` and edit it if the backend runs on another host or
port:

```bash
cp .env.example .env
```

Vite only reads `.env` at startup, so restart `npm run dev` after changing it.
The value is baked in at build time for `npm run build`.

The sidebar shows whether the configured backend is reachable, so a
misconfigured URL is visible before you submit a trace.

## Views

- **`/` — New trace.** Enter a Bitcoin address and choose a hop depth (default 4,
  matching the backend). Submitting calls `POST /api/trace`. Traces run against
  live blockchain data, so the wait screen reports elapsed time rather than
  implying the call should be instant.
- **`/cases` — Cases.** Every trace that has been run, from `GET /api/cases`.
- **`/cases/:id` — Case detail.** The full result from `GET /api/cases/{id}`:
  attribution summary, the 3D fund-flow graph, the hop trail, and a link to the
  generated PDF report.

## Reading the fund-flow graph

Drag to rotate, scroll to zoom, right-drag to pan. Click a node to see its full
address and where it first appears in the hop trail.

- **Cyan node** — the address you queried. It turns **green** when the trace
  resolved a VASP for it. The engine evaluates attribution against the query
  address and its co-spend cluster only, never against downstream hop addresses,
  so a match always belongs to this node and no hop node is ever highlighted as
  the match.
- **Slate nodes** — addresses reached by following outgoing spends, shaded
  progressively darker with hop depth.
- **Edges** — one per hop record, directed along the flow of funds, labelled on
  hover with the transaction hash and BTC amount.

### Why some edges pass through a "payer not recorded" node

A hop record is `{hop_index, address, tx_hash, timestamp, amount_btc}`. It says
how far from the seed an address was reached and which transaction paid it, but
not which address sent the funds.

At `hop_index` 0 that is unambiguous: the trace starts at the query address, so
those edges are drawn directly from it. Deeper in the trace, the payer is one of
the addresses at the previous hop, and when there is more than one candidate the
data does not say which. Rather than guess an edge that may not correspond to a
real transfer, those edges route through a single explicit "payer not recorded"
node per hop level, and every candidate at the previous level links into it.

This is a limitation of the trace contract, not of the graph. Adding a
`from_address` (or `source_address`) field to the hop schema would let the graph
draw the true parent for every edge.

## Notes on what the results mean

Attribution runs against a curated seed list of publicly documented exchange
addresses, so coverage is partial by design. A match is a lead worth
investigating — a likely service relationship — not an identification of a person
and not an indication of wrongdoing. Confidence is shown as a bounded score
(`0.00`–`1.00`), deliberately not as a percentage certainty about a named entity.

Risk flags are heuristic signals computed by the backend from hop timing and
fan-out. The dashboard labels them as signals and displays them; it does not
compute or reinterpret them.

### Empty hop trails are a valid result

Tracing follows only what an address has **spent**, never what it has received.
A deposit-only or reserve address can have extensive transaction history and
still return no hops. The case view says so explicitly instead of showing an
empty graph. The well-known Binance address
`34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo` is a good example — it resolves to a VASP
with an empty hop trail.

### Traces can take minutes

The engine makes one live mempool.space request per address it walks, with
retries and backoff, and fan-out grows quickly with hop depth. A busy address at
depth 2 has been measured at around three minutes. There is no client-side
timeout on `POST /api/trace` for that reason; the wait screen shows elapsed time
so a long trace is legible rather than looking frozen.
