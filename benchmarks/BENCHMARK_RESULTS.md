# Elliptic Benchmark Results (Task 7)

> **Correction / Methodological Note (Task 7 Follow-Up):**  
> The initial Task 7 adapter synthesized one transaction per outgoing edge (each with 1 output), which made `max_branches_per_tx=5` in `trace_hops()` structurally unreachable because `len(outputs)` was always 1 per transaction dict. This corrected benchmark uses a batched one-transaction-per-node adapter that places all outgoing destination edges into a single `outputs` list (with `tx_hash` prefixed `elliptic_node_tx::{node_id}`). This faithfully mirrors real high-fanout Bitcoin transactions and properly exercises the `max_branches_per_tx` safeguard. All metrics below represent fresh recomputed numbers from the full 203,769-node dataset.

---

## What this benchmark does and does NOT measure

### Out of Scope / Explicit Non-Goals:
- **NO VASP Attribution Accuracy:** The Elliptic dataset contains no VASP labels of any kind. This benchmark does not compute, report, or imply any VASP matching accuracy.
- **NO Address Clustering / CIOH Benchmark:** The Elliptic dataset contains no raw transaction input/output (vin/vout) address lists — only anonymized transaction feature vectors and a transaction-to-transaction edgelist. `clustering.py` is not exercised against this data.
- **NO Illicit/Licit Classification:** Elliptic's `class` label is neither used nor correlated with engine outputs (which is strictly Person B / `risk_flags` territory).
- **Synthetic Placeholder Fields:** In the adapter, `amount_btc` is set to `0.0`, `timestamp` is `None`, and `tx_hash` is prefixed `elliptic_node_tx::`. These are placeholders; this benchmark does not measure amount or timestamp logic.

### What this Benchmark Measures:
A **graph-traversal robustness and performance benchmark** of the real, unmodified `trace_hops()` function (`tracing_engine/hop_tracer.py`), run against the real transaction-flow graph structure from the Kaggle Elliptic Bitcoin dataset (`elliptic_txs_edgelist.csv`). Each Elliptic `txId` is used as a stand-in "address" to evaluate BFS traversal across 203,769 nodes and 234,355 edges under realistic Bitcoin graph branching topologies.

---

## 1. Crash-Free Completion Rate

| Metric | max_hops = 2 | max_hops = 4 |
| :--- | :--- | :--- |
| **Total Seed Nodes Tested** | 203,769 | 203,769 |
| **Successfully Completed Traces** | 203,769 | 203,769 |
| **Crash-Free Completion Rate** | **100.0000%** | **100.0000%** |
| **Unhandled Exceptions** | 0 | 0 |

*Exception Breakdown:*
- `max_hops=2`: None (0 unhandled exceptions across all runs)
- `max_hops=4`: None (0 unhandled exceptions across all runs)

---

## 2. Traversal Size Distribution

### Hops Discovered (`len(hops_record)`):
| max_hops | Min | Median | Max | Mean | p95 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **max_hops = 2** | 0 | 2.0 | 30 | 2.136 | 5 |
| **max_hops = 4** | 0 | 3.0 | 350 | 4.134 | 11 |

### Unique Addresses Visited (Seed + Destination Nodes):
| max_hops | Min | Median | Max | Mean | p95 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **max_hops = 2** | 1 | 3.0 | 31 | 3.108 | 6 |
| **max_hops = 4** | 1 | 4.0 | 163 | 4.827 | 12 |

---

## 3. Branch-Limit Trigger Rate & Fan-Out Analysis

- **Per-Trace Branch Limit Trigger Rate (`max_branches_per_tx=5`):**
  - `max_hops = 2`: **2.87%** (5,844 of 203,769 total traces triggered the branch cap)
  - `max_hops = 4`: **4.38%** (8,918 of 203,769 total traces triggered the branch cap)
- **Safeguard Effectiveness on High-Fanout Nodes:**
  - Maximum raw out-degree observed for any single node in the dataset: **472** outgoing transaction edges.
  - Nodes with out-degree > 5 in raw dataset: **1,963** (1.18% of all 166,345 source nodes).
  - Configured transaction fan-out safeguard cap in `trace_hops()`: **5**.
  - **Forensic Impact:** Without this cap, high-fanout consolidation nodes (such as the node with 472 outputs) would cause combinatorial explosion in BFS queue size. With `max_branches_per_tx=5`, `trace_hops()` bounded the maximum hops discovered per trace at 350 (at max_hops=4), maintaining strict linear execution bounds.
- **Interaction with Task 9 hop-dedup fix:** After the Task 9 ancestor-aware
  fix, repeat real destinations now correctly consume one of the 5
  `max_branches_per_tx` slots (previously they were filtered out before
  reaching the cap). This is why the max "Hops Discovered" figure rose
  (203→350) while the max "Unique Addresses Visited" figure fell (204→163)
  compared to the pre-fix benchmark run: more real repeat-payment activity is
  now captured, at the cost of slightly less new-address discovery on
  already-cap-constrained high-fanout nodes. This is expected and correct.

---

## 4. DAG & Cycle-Handling Analysis

- **Topological Acyclicity Verification:** **PASSED (Strict Directed Acyclic Graph - DAG)**
  - Total graph nodes checked: 203,769
  - Topological sort order verified: 203,769 / 203,769 nodes resolved with zero remaining cyclic dependencies.
- **Cycle-Avoidance Note:** Because the Elliptic Bitcoin transaction graph is strictly acyclic, this dataset cannot exercise the visited-address cycle-avoidance path in `trace_hops()`. Cycle avoidance itself was already covered and verified by Task 3's dedicated unit tests.

---

## 5. Performance at Scale

| max_hops | Mean Time / Trace (ms) | p95 Time / Trace (ms) | Throughput (traces / sec) |
| :--- | :--- | :--- | :--- |
| **max_hops = 2** | **0.0363 ms** (36.33 µs) | **0.0875 ms** | **27,527** |
| **max_hops = 4** | **0.0853 ms** (85.29 µs) | **0.2022 ms** | **11,725** |

- **Runtime Scaling (2→4 hops):** Scaling ratio of mean wall-clock times is **2.35x**, demonstrating sub-linear to mild linear growth with no exponential degradation.

---

## Reproducibility Commands

To re-run this benchmark independently:

```bash
# Ensure dataset exists at data/elliptic/elliptic_txs_edgelist.csv
python benchmarks/run_elliptic_benchmark.py
```
