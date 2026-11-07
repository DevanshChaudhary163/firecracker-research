# Firecracker MicroVM Cold Start Benchmarks

[![Report](https://img.shields.io/badge/Research_Report-PDF-red?style=flat&logo=adobeacrobatreader)](Firecracker_REAP_Benchmark_Report.pdf)
[![Terminal Log](https://img.shields.io/badge/Raw_Terminal_Log-pane.txt-lightgrey?style=flat&logo=gnubash)](pane.txt)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python)](https://www.python.org/)
[![Firecracker](https://img.shields.io/badge/Hypervisor-Firecracker%20v1.17.0-orange?style=flat)](https://firecracker-microvm.github.io/)

Empirical research and benchmarking suite evaluating microVM cold start optimization in **AWS Firecracker**. We compare **Standard File-backed Snapshots**, **Lazy Userfaultfd (Demand Paging)**, and **REAP (Record and Prefetch)** on a real Ubuntu testbed.

---

## Empirical Results (30 Trials per Technique)

All measurements below are extracted directly from our live terminal benchmark runs ([`pane.txt`](pane.txt)):

| Restoration Technique | Trials | Mean | Median | Min | Max | P95 Tail | Std Dev | Working Set / Prefetch |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **File-backed Snapshot** | 30 | **41.49 ms** | 42.17 ms | 32.48 ms | 44.58 ms | **44.31 ms** | 2.72 ms | N/A (Host page cache) |
| **Lazy UFFD (Demand Paging)** | 30 | **103.07 ms** | 114.95 ms | 63.22 ms | 123.57 ms | **122.31 ms** | 20.14 ms | 0 pages (On-demand traps) |
| **REAP (Record & Prefetch)** | 30 | **79.37 ms** | 91.61 ms | 48.21 ms | 95.66 ms | **95.41 ms** | 19.22 ms | **2,024 pages (7.9 MiB in 3.4 ms)** |

### Key Takeaways
1. **The Lazy Paging Bottleneck:** Pure on-demand userfaultfd paging increases latency to **103.07 ms** (2.5x slower than snapshot) due to round-trip userfaultfd socket context switches for every accessed page.
2. **REAP Delivers a 23% Speedup:** By recording the function's working set (**2,024 pages / 7.906 MiB** out of 512 MiB total RAM) and prefetching it in **3.428 ms**, REAP reduces mean latency from 103.07 ms down to **79.37 ms** and drops P95 tail latency by **26.9 ms** to **95.41 ms**.
3. **Snapshot Baseline:** File-backed snapshot restoration remains fastest (**41.49 ms**) because memory mapping is managed entirely inside host kernel space.

📄 **Publication Summary**: See the clean 1-page report in [`Firecracker_REAP_Benchmark_Report.pdf`](Firecracker_REAP_Benchmark_Report.pdf).

---

## How Everything Was Done (Workflow & Progress)

1. **Testbed Setup**:
   - Host: Ubuntu 24.04 LTS (Linux kernel 6.18.56+ x86_64, GenuineIntel CPU).
   - Firecracker v1.17.0 running a minimized Ubuntu 24.04.5 LTS guest (1 vCPU, 512 MiB RAM).
   - Guest serial runner: [`runner.sh`](runner.sh) listening on `ttyS0` for synchronized `PING/PONG` and `RUN` commands.
2. **Snapshot Creation**:
   - Started VM, verified `RUNNER_READY`, paused microVM (`PATCH /vm {"state":"Paused"}`), and dumped full snapshot: `vm_state` (14 KB) and `vm_memory` (512 MiB).
3. **Phase 1: Initial Baseline Prototype ([`benchmark_original.py`](benchmark_original.py))**:
   - Single-trial restore. Yielded **89.975 ms** (skewed by a hardcoded `time.sleep(0.05)`).
4. **Phase 2: Synchronized 30-Trial Snapshot Benchmark ([`benchmark_snapshot.py`](benchmark_snapshot.py))**:
   - Replaced sleep delay with an active bidirectional `PING`/`PONG` handshake over the PTY serial line.
   - Ran 30 trials with atomic rootfs disk resetting. Mean: **41.494 ms**, StdDev: **2.715 ms**.
   - Processed with [`analyze_snapshot.py`](analyze_snapshot.py).
5. **Phase 3: Userfaultfd & REAP Harness ([`benchmark_uffd.py`](benchmark_uffd.py))**:
   - **Record mode (`--mode record`):** Captured memory fault offsets (`record_001.log`) -> extracted 2,024 unique pages (7.906 MiB) into `working_set_offsets.txt`.
   - **REAP mode (`--mode reap`):** Proactively faulted all 2,024 pages into guest memory via `bin/uffd_handler_reap` before unpausing. Prefetch completed in **3.428 ms**.
   - **Lazy UFFD mode (`--mode uffd`):** Evaluated pure demand-paging baseline.

---

## Repository Files

```
.
├── benchmark_original.py   # Initial single-trial prototype
├── benchmark_snapshot.py   # Synchronized 30-trial snapshot benchmark (PING/PONG handshake)
├── benchmark_uffd.py       # Unified UFFD harness: record, uffd, and reap modes
├── analyze_snapshot.py     # Statistical post-processor (Mean, Median, StdDev, P95)
├── results.csv             # Exact empirical latency data for all 90 benchmark trials
├── pane.txt                # Raw Ubuntu terminal log capturing all commands & outputs
├── runner.sh               # Guest workload runner script (/root/benchmarks/runner.sh)
├── memrunner.c             # Static memory scanning workload for memory footprint tests
├── generate_report.py      # Python script to compile the PDF report & charts
├── Firecracker_REAP_Benchmark_Report.pdf # 1-page research report
└── README.md
```

---

## Quick Execution

```bash
# 1. Run 30-trial snapshot benchmark
python3 benchmark_snapshot.py

# 2. Run statistical analysis
python3 analyze_snapshot.py

# 3. Record working-set pages
python3 benchmark_uffd.py --mode record --trials 1

# 4. Run 30-trial REAP prefetch benchmark
python3 benchmark_uffd.py --mode reap --trials 30

# 5. Run 30-trial Lazy UFFD benchmark
python3 benchmark_uffd.py --mode uffd --trials 30

# 6. Rebuild PDF report
python3 generate_report.py
```

---

