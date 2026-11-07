# Firecracker MicroVM Cold Start Optimization & REAP Benchmarks

[![Report](https://img.shields.io/badge/Research_Report-PDF-red?style=flat&logo=adobeacrobatreader)](Firecracker_REAP_Benchmark_Report.pdf)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python)](https://www.python.org/)
[![Firecracker](https://img.shields.io/badge/Hypervisor-Firecracker-orange?style=flat)](https://firecracker-microvm.github.io/)
[![Research](https://img.shields.io/badge/Paper-ASPLOS%20'21%20REAP-purple?style=flat)](https://dl.acm.org/doi/10.1145/3445814.3446714)

Empirical evaluation and benchmarking harness for optimizing serverless function cold starts in **AWS Firecracker MicroVMs**. We compare **Standard File-backed Snapshots**, **Lazy Userfaultfd (Demand Paging)**, and **REAP (Record and Prefetch)**.

---

## Key Results Summary (30-Trial Evaluation)

| Technique | Ready Latency (Mean) | Invocation Latency (Mean) | Total Latency (Mean) | P95 Tail Latency | Prefetched Pages |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **File-backed Snapshot** | 5.76 ms | 1.98 ms | **7.74 ms** | 8.41 ms | 0 (N/A) |
| **Lazy UFFD (Demand)** | 4.12 ms | 12.85 ms | **16.97 ms** | 19.42 ms | 0 |
| **REAP (Prefetched)** | 5.43 ms | 2.15 ms | **7.58 ms** | **8.12 ms** | **412 pages** |

> **Key Takeaway:** Lazy demand paging reduces hypervisor setup time but causes a **548% slowdown** during function execution due to userfaultfd context switches. **REAP** eliminates this penalty by proactively loading the recorded working set (412 pages in ~1.31 ms) before VM unpause, achieving the lowest P95 tail latency (**8.12 ms**).

📄 **Full Analysis**: See the 2-page publication summary in [`Firecracker_REAP_Benchmark_Report.pdf`](Firecracker_REAP_Benchmark_Report.pdf).

---

## How We Are Doing Everything (Methodology)

1. **Active Handshake Protocol (`PING`/`PONG`)**:
   Instead of arbitrary sleep delays, the harness communicates directly with the guest serial console over a pseudo-terminal (`pty.openpty()`), strictly decoupling:
   - `ready_ms`: Time from process launch and snapshot load to guest runtime availability.
   - `invocation_ms`: Time from function trigger to execution completion.
2. **REAP Workflow**:
   - **Step 1 (Record):** Run function once with `uffd_handler_record` to capture accessed guest page offsets into `working_set_offsets.txt`.
   - **Step 2 (Prefetch):** Restore subsequent instances with `uffd_handler_reap`, issuing bulk `UFFDIO_COPY` calls to pre-populate working-set memory prior to execution.
3. **Statistical Rigor**:
   Every configuration is evaluated over 30 trials with fresh disk state restoration (`shutil.copyfile`), tracking Mean, Median, StdDev, and P95 latency.

---

## Repository Structure

```
.
├── benchmarks/
│   ├── benchmark_original.py    # Baseline v1: Naive single-trial snapshot restore
│   ├── benchmark_snapshot.py    # Baseline v2: 30-trial synchronized snapshot benchmark
│   ├── benchmark_uffd.py        # Unified harness: supports record, uffd, and reap modes
│   ├── analyze_snapshot.py      # Statistical post-processor (Mean, P95, StdDev)
│   └── benchmark.py             # Reference snapshot test script
├── docs/
│   ├── PROGRESSION.md           # Detailed chronicle tracking chat & code evolution
│   └── ARCHITECTURE.md          # System diagram, UFFD socket flow & memory models
├── results/
│   ├── sample_snapshot.csv      # 30-trial sample dataset for snapshot restoration
│   └── sample_uffd_comparison.csv # Comparative performance metrics
├── scripts/
│   ├── generate_report.py       # Compiles publication-ready PDF report with charts
│   └── charts/                  # Generated latency breakdown & P95 figures
├── Firecracker_REAP_Benchmark_Report.pdf # Comprehensive 2-page research report
└── README.md
```

---

## Quickstart & Execution

### Prerequisites (Linux with KVM)
- Linux kernel 5.4+ with `KVM` and `userfaultfd` support
- `firecracker` binary in `$PATH`
- Python 3.8+ with `curl`

### Running the Benchmarks

```bash
# 1. Benchmark standard file-backed snapshot restoration (30 trials)
python3 benchmarks/benchmark_snapshot.py

# 2. Analyze statistical metrics (Mean, Median, P95)
python3 benchmarks/analyze_snapshot.py

# 3. Record working-set page offsets
python3 benchmarks/benchmark_uffd.py --mode record --trials 1

# 4. Evaluate lazy demand-paging baseline
python3 benchmarks/benchmark_uffd.py --mode uffd --trials 30

# 5. Evaluate REAP prefetching
python3 benchmarks/benchmark_uffd.py --mode reap --trials 30

# 6. Rebuild the PDF research report
python3 scripts/generate_report.py
```

---

## Author & Research Progress
- **Author:** [Devansh Chaudhary](https://github.com/DevanshChaudhary163)
- **Institution:** Department of Electrical Engineering, Indian Institute of Technology Indore (IIT Indore)
- **Focus:** Serverless MicroVM Virtualization, Memory Subsystems, and Cold Start Latency Reduction
