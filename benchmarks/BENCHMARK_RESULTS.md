# Elliptic Benchmark Results (Task 7)

## What this benchmark does and does NOT measure

### Out of Scope / Explicit Non-Goals:
- **NO VASP Attribution Accuracy:** The Elliptic dataset contains no VASP labels of any kind. This benchmark does not compute, report, or imply any VASP matching accuracy.
- **NO Address Clustering / CIOH Benchmark:** The Elliptic dataset contains no raw transaction input/output (vin/vout) address lists — only anonymized transaction feature vectors and a transaction-to-transaction edgelist. `clustering.py` is not exercised against this data.
- **NO Illicit/Licit Classification:** Elliptic's `class` label is neither used nor correlated with engine outputs (which is strictly Person B / `risk_flags` territory).
- **Synthetic Placeholder Fields:** In the adapter, `amount_btc` is set to `0.0`, `timestamp` is `None`, and `tx_hash` is prefixed `elliptic_edge::`. These are placeholders; this benchmark does not measure amount or timestamp logic.

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
| **max_hops = 2** | 0 | 2.0 | 671 | 2.308 | 5 |
| **max_hops = 4** | 0 | 3.0 | 794 | 4.322 | 12 |

### Unique Addresses Visited (Seed + Destination Nodes):
| max_hops | Min | Median | Max | Mean | p95 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **max_hops = 2** | 1 | 3.0 | 672 | 3.308 | 6 |
| **max_hops = 4** | 1 | 4.0 | 795 | 5.322 | 13 |

---

## 3. Branch-Limit Trigger Rate & Fan-Out Analysis

- **Per-Transaction Branch Limit Trigger Rate (`max_branches_per_tx=5`):** 0.00% (max_hops=2) and 0.00% (max_hops=4).
- **Synthesized Per-Transaction Fan-Out:** In the adapter mapping, each synthesized transaction represents exactly one directed edge with 1 output, meaning individual transaction output lists do not exceed 1 output.
- **Underlying Graph Node Out-Degree (Fan-Out):**
  - Maximum out-degree observed for any single node in the raw dataset: **472** outgoing transaction edges.
  - Nodes with out-degree > 5: **1,963** (1.18% of all 166,345 source nodes).
  - Configured transaction fan-out safeguard cap in `trace_hops()`: **5**.

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
| **max_hops = 2** | **0.0484 ms** (48.44 µs) | **0.0963 ms** | **20,642** |
| **max_hops = 4** | **0.1078 ms** (107.80 µs) | **0.1912 ms** | **9,276** |

- **Runtime Scaling (2→4 hops):** Scaling ratio of mean wall-clock times is **2.23x**, showing sub-linear to mild linear growth with no signs of exponential runtime blowup across deeper traversal depths.

---

## Reproducibility Commands

To re-run this benchmark independently:

```bash
# Ensure dataset exists at data/elliptic/elliptic_txs_edgelist.csv
python benchmarks/run_elliptic_benchmark.py
```
