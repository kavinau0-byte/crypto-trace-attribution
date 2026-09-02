# Elliptic Bitcoin Dataset

This directory contains the Kaggle Elliptic Bitcoin dataset files used for the Task 7 graph-traversal performance and robustness benchmarks (`benchmarks/run_elliptic_benchmark.py`).

## Dataset Source
- **Kaggle URL:** [https://www.kaggle.com/datasets/ellipticco/elliptic-data-set](https://www.kaggle.com/datasets/ellipticco/elliptic-data-set)
- **Primary File Used:** `elliptic_txs_edgelist.csv` (directed transaction-flow edge list with columns `txId1`, `txId2`)

## Storage & Licensing Notice
Raw dataset CSV and ZIP files are gitignored and not committed to this repository due to file size and dataset licensing/redistribution terms. To run benchmarks locally, download `elliptic_txs_edgelist.csv` from Kaggle and place it in this directory (`data/elliptic/elliptic_txs_edgelist.csv`).
