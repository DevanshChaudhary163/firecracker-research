# Research Progression & Development Chronicle

This document tracks the iterative evolution of our Firecracker microVM benchmarking and optimization research, capturing the progression through each stage of development.

---

## 1. Initial State: Naive Snapshot Restore (`benchmark_original.py` / `benchmark.py`)

### Initial Goal
Validate that Firecracker microVMs can be restored from a pre-computed memory snapshot and execute a simple guest workload (`hello`).

### Limitations & Flaws Identified
- **Arbitrary Delay Flaw**: The script relied on `time.sleep(0.05)` after unpausing the VM (`PATCH /vm {"state": "Resumed"}`) before transmitting the `RUN hello` command over the PTY serial line. This arbitrary 50ms delay masked true boot/readiness dynamics and skewed latency calculations.
- **Single-Trial Jitter**: Only ran a single trial (`REQUEST_ID = "1"`). Serverless cold starts exhibit significant tail latency and system jitter; a single run provided zero statistical confidence.
- **Confounded Metrics**: VM restore time, hypervisor initialization, guest scheduling, and function execution were lumped into a single opaque `elapsed_ms` measurement.
- **External Shell Dependencies**: Used `subprocess.run(["cp", ...])` instead of atomic, portable Python I/O primitives for rootfs resetting.

---

## 2. Iteration 1: Rigorous Multi-Trial Benchmarking (`benchmark_snapshot.py`)

### Key Enhancements & Refinements
- **Active Synchronized Handshake (`PING`/`PONG`)**:
  Replaced the blind `sleep(0.05)` with an active bidirectional handshake over the guest pseudo-terminal:
  ```python
  os.write(master, b"PING\r")
  ready = read_until(master, "PONG", timeout=10)
  ```
  This cleanly decouples the cold start into two distinct phases:
  1. `ready_ms`: Time from Firecracker process launch and `/snapshot/load` until the guest runtime is active and responding.
  2. `invocation_ms`: Time from command dispatch (`RUN hello <id>`) until function execution completes (`BENCHMARK_COMPLETE`).
- **30-Trial Statistical Regime**: Implemented automated execution across 30 identical trials, starting each run from an identical disk image (`shutil.copyfile`).
- **Structured Metric Persistence**: Logged detailed metrics per trial directly to CSV (`results/benchmarks/snapshot.csv`).

---

## 3. Iteration 2: Statistical Post-Processing (`analyze_snapshot.py`)

### Objective
Process empirical trial logs to quantify latency distribution, variance, and tail performance.

### Metrics Computed
- **Central Tendency**: Arithmetic Mean and Median.
- **Dispersion & Variance**: Standard Deviation (jitter across consecutive microVM launches).
- **Tail Latency**: 95th Percentile (P95) computed using rank-ordered indices:
  $$\text{Index}_{\text{P95}} = \min(n - 1, \max(0, \lceil 0.95 \times n \rceil - 1))$$

---

## 4. Iteration 3: Memory Optimization & REAP Harness (`benchmark_uffd.py`)

### Research Motivation
In high-density serverless clusters, loading full VM memory images into host RAM upfront causes severe memory overcommitment and disk I/O bottlenecks. However, switching to standard lazy paging via Linux `userfaultfd` causes function execution to crawl due to page fault traps.

To evaluate **REAP (Record and Prefetch)**, we implemented a unified harness with three execution modes:

```
                            +-----------------------------------+
                            |        benchmark_uffd.py          |
                            +-----------------+-----------------+
                                              |
               +------------------------------+-------------------------------+
               |                              |                               |
       [ Mode 1: record ]             [ Mode 2: uffd ]                [ Mode 3: reap ]
               |                              |                               |
  Runs uffd_handler_record        Runs uffd_handler (lazy)        Runs uffd_handler_reap
  Captures memory fault traces    Serves on-demand page faults    Proactively prefetches
  Dumps working_set_offsets.txt   High invocation trap overhead   working_set_offsets.txt
```

### Protocol & Synchronization Enhancements
1. **Daemon Management**: Launches independent `uffd_handler_*` processes over UNIX socket `/tmp/fc-reap-handler.sock` before initializing Firecracker.
2. **Prefetch Coordination**: In `reap` mode, monitors handler logs for `PREFETCH_COMPLETE pages=<n> elapsed_ms=<t>` before unpausing the VM.
3. **Safe Teardown**: Guaranteed cleanup of child PIDs and UNIX sockets via structured `try...finally` blocks.
4. **Multi-Metric Telemetry**: Tracks `ready_ms`, `invocation_ms`, `total_ms`, `prefetch_ms`, and `prefetched_pages`.
