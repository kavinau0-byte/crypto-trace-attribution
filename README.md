# SIH26182 — Tracing Engine (Automated Cryptocurrency Wallet Attribution)

> **Component:** Blockchain Tracing Engine (Person A)  
> **Target Blockchain:** Bitcoin (UTXO Model)  
> **Branch:** `feature/tracing-engine`  
> **Integration Entrypoint:** `tracing_engine.engine.trace_wallet(address, max_hops=4)`

---

## 1. Overview & Architecture

The **Tracing Engine** performs automated forward-hop tracing and entity attribution for unknown Bitcoin wallet addresses to identify their nearest Virtual Asset Service Provider (VASP).

### Directory Layout

```
crypto-trace-attribution/
├── tracing_engine/
│   ├── __init__.py          # Package exports (trace_wallet, TraceResult, build_clusters, etc.)
│   ├── config.py            # API base URLs, timeouts, retry settings, backoff factors
│   ├── schema.py            # Dataclasses & typed dicts matching the JSON contract exactly
│   ├── fetcher.py           # mempool.space API client with backoff retries & normalization
│   ├── hop_tracer.py        # Forward BFS traversal engine for Bitcoin UTXO graphs
│   ├── clustering.py        # Common-Input-Ownership Heuristic (CIOH) clustering & CoinJoin guard
│   ├── vasp_matcher.py      # [STUB - Day 5] VASP seed database & tag matcher
│   ├── confidence.py        # [STUB - Days 5-6] Transparent deterministic confidence calculator
│   └── engine.py            # Master orchestrator exposing trace_wallet()
├── data/
│   └── vasp_seed_list.json  # Curated VASP seed database scaffold (for Days 3-4)
├── tests/
│   ├── test_fetcher.py      # Smoke tests and JSON contract compliance verification
│   └── test_clustering.py   # Unit tests for CIOH clustering, singleton sets, and CoinJoin guard
├── requirements.txt         # Lightweight dependencies (requests, pytest)
└── README.md                # Documentation, API usage, and forensic limitations
```

---

## 2. JSON Integration Contract (Person A / Person B Boundary)

`trace_wallet(address: str, max_hops: int = 4) -> dict` produces the strict JSON contract required by Person B's platform/dashboard:

```json
{
  "query_address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
  "chain": "bitcoin",
  "hops": [
    {
      "hop_index": 0,
      "address": "1DestinationAddress...",
      "tx_hash": "9f8e7d8c...",
      "timestamp": "2026-09-01T10:08:32Z",
      "amount_btc": 0.45200000
    }
  ],
  "matched_vasp": null,
  "confidence": 0.0,
  "match_method": "unresolved",
  "risk_flags": []
}
```

### Field Ownership Boundary
- **Person A (Tracing Engine):** Owns `query_address`, `chain`, `hops`, `matched_vasp`, `confidence`, `match_method`.
- **Person B (Platform / Investigator Tools):** Owns `risk_flags`. Person A always initializes `risk_flags: []` and never modifies it.
- **`match_method` Values:** One of `"direct_tag"`, `"cluster_match"`, `"unresolved"`.

---

## 3. Quickstart & Usage

### Prerequisites
- Python 3.10+
- Dependencies in `requirements.txt`:
  ```bash
  pip install -r requirements.txt
  ```

### Running the Tracing Engine

```python
from tracing_engine import trace_wallet, build_clusters
import json

# Trace a Bitcoin address up to 3 hops
result = trace_wallet("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", max_hops=3)

print(json.dumps(result, indent=2))
```

### Running Tests

```bash
python -m pytest -v tests/
```

---

## 4. Blockchain API Details

- **Primary Provider:** [mempool.space REST API](https://mempool.space/docs/api/rest)
  - Endpoints:
    - Address Transactions: `GET /api/address/{address}/txs` (used by `fetcher.py` and `hop_tracer.py`)
    - Transaction Details: `GET /api/tx/{txid}` (used by `clustering.py` to retrieve full co-spending input UTXO lists when clustering from raw hop records or transaction identifiers)
  - Auth: No API key required for standard endpoints.
  - Resilience: Automatic exponential backoff retries (max 3 retries, factor 2.0) on HTTP 429 / 5xx. Graceful handling of invalid addresses/hashes (HTTP 400/404) and unconfirmed outputs.
- **Secondary Fallback:** [Blockchair API](https://api.blockchair.com/bitcoin) (configured in `config.py`).
- **Clustering API Fetches Note:** `hop_tracer.py` records only the single destination hop followed per branch, not all co-spending inputs. Therefore, `clustering.py` makes dedicated transaction detail fetches when resolving transaction input sets for clustering.

---

## 5. Known Limitations & Forensic Disclaimers

1. **Common-Input-Ownership Heuristic (CIOH) Limitations:**  
   This clustering is a heuristic based on common-input-ownership. It is **NOT** proof of common wallet ownership. Known failure mode: CoinJoin/mixing transactions can cause false-positive merges between unrelated addresses. A coarse input-count guard (`MAX_INPUTS_FOR_CLUSTERING = 5`) partially mitigates this by skipping transactions with >5 inputs, but does not eliminate all multi-party mixing risks.
2. **Bitcoin UTXO Model & Forward-Trace Heuristic:**  
   Bitcoin operates on the Unspent Transaction Output (UTXO) model rather than account-based balances. A single transaction may combine multiple inputs and distribute funds across multiple outputs (e.g. payment recipient + change address).
3. **Curated Seed Coverage (No Global Completeness Claim):**  
   The VASP address registry is a curated seed list (`data/vasp_seed_list.json`) intended for demonstration and evaluation. It does not represent exhaustive global exchange wallet coverage.
4. **Transparent Confidence Scoring:**  
   Confidence scores are computed via deterministic, documented formulas based on verifiable signals (hop distance decay, cluster purity, and direct tagging certainty) — never black-box guesses.
5. **Investigative Evidence Notice:**  
   Attribution results generated by this tool constitute investigative leads and heuristic evidence, **not legal proof** of entity identity, wallet ownership, or liability.
6. **No Government Portal Integration:**  
   This prototype is an independent blockchain analytics engine and does not connect to or fabricate any connection to government reporting portals (e.g., SAHYOG).
