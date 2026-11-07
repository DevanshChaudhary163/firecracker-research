# Firecracker MicroVM Cold Start Optimization & REAP Benchmarks

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat&logo=python)](https://www.python.org/)
[![Firecracker](https://img.shields.io/badge/Hypervisor-Firecracker%20v1.17.0-orange?style=flat)](https://firecracker-microvm.github.io/)
[![Linux](https://img.shields.io/badge/Linux-Ubuntu%2024.04%20LTS-E95420?style=flat&logo=ubuntu)](https://ubuntu.com/)

An empirical research study and benchmarking suite evaluating techniques to reduce **cold start latency** in serverless microVMs (**AWS Firecracker**). This repository contains benchmarking scripts, synchronization routines, real testbed metrics, and an automated report generator comparing **Standard File-backed Snapshots**, **Lazy Userfaultfd (Demand Paging)**, and **REAP (Record and Prefetch)**.

---

## 📖 Background & Concepts 

If you are new to serverless cloud systems or operating system virtualization, here is an intuitive breakdown of the problem this research addresses:

### 1. What is Serverless & What is a "Cold Start"?
In traditional cloud hosting, you rent a virtual server that runs 24/7, paying for CPU and RAM even when nobody visits your site. 

In **Serverless Computing** (like **AWS Lambda** or **Google Cloud Functions**):
- You only upload your application code (a function).
- The cloud provider only runs your code when an event occurs (e.g., a user makes an HTTP request).
- When traffic drops to zero, your function is shut down so you pay nothing.

**The Problem (The Cold Start):**
- **Warm Start:** If an instance of your function is already running in memory from a recent request, incoming calls execute immediately (**< 5 ms**).
- **Cold Start:** If no instance is active (e.g., sudden traffic burst or first request of the day), the cloud platform must launch a fresh execution environment from scratch. Booting a traditional operating system and initializing runtimes can take hundreds of milliseconds to several seconds—introducing unwanted latency that degrades user experience.

### 2. Why AWS Firecracker & MicroVMs?
Cloud providers need to run code from thousands of different customers on the same physical server.
- **Containers (Docker):** Lightweight and boot quickly, but they share the host Linux kernel. A single kernel vulnerability can allow malicious code to escape and compromise neighboring containers.
- **Traditional VMs (QEMU):** Provide strong hardware isolation, but emulate hundreds of legacy PC devices (PCI buses, ACPI, IDE controllers), making them slow to boot and memory-heavy.

Amazon designed **Firecracker** to solve this:
- **Micro-Virtual Machines (microVMs):** Runs on top of the Linux Kernel-based Virtual Machine (**KVM**).
- **Minimalist Emulation:** Strips away all legacy PC peripherals. A microVM only exposes minimal virtual devices (serial console, virtio-net, virtio-block). It boots in fractions of a second while maintaining the strict security isolation of a real virtual machine.

### 3. What is Snapshot Restoration?
Even with Firecracker's speed, booting an entire Linux kernel and initializing runtimes on every single cold start takes 100–300 ms.

To bypass this overhead, modern serverless platforms use **memory snapshotting**:
1. Boot the microVM once and let the function runtime initialize completely.
2. Pause the microVM and freeze its state into two files:
   - `vm_state` (~14 KB): CPU register values, virtual device states, and hypervisor configuration.
   - `vm_memory` (~512 MB): An exact byte-for-byte memory image of the guest's RAM.
3. When a cold start arrives, Firecracker skips the boot sequence entirely—it simply loads the saved `vm_state` and `vm_memory` from disk, resuming execution in milliseconds.

---

## ⚡ The Memory Dilemma: Snapshots vs. Lazy Paging vs. REAP

While snapshots drastically reduce cold start times, how the host hypervisor manages the guest's memory snapshot creates a difficult trade-off:

```
                            +-----------------------------------------+
                            | How Should We Restore Guest VM Memory?  |
                            +--------------------+--------------------+
                                                 |
         +---------------------------------------+---------------------------------------+
         |                                       |                                       |
[ Method 1: File-backed Snapshot ]     [ Method 2: Lazy Userfaultfd ]           [ Method 3: REAP (Record & Prefetch) ]
Memory mapped directly from host disk.   Zero memory loaded upfront.              Record working set (2,024 pages).
Host kernel demand-pages via page cache. Traps missing pages to userspace UFFD.  Proactively prefetches pages in 3.4ms!
- Fast single-VM restore (41.5 ms).     - Instant VM setup.                      - Fast invocation (79.4 ms).
- High RAM footprint under concurrency. - Severe execution penalty (103.1 ms)!   - Low memory footprint & no trap storm!
```

### Method 1: File-backed Snapshot (Baseline)
- **Mechanism:** Firecracker maps (`mmap`) the snapshot file `vm_memory` directly into the guest address space on the host.
- **Pros:** Fast for single-VM benchmarks (**~41.5 ms**). The host Linux kernel handles paging transparently.
- **Cons:** In a high-density production cloud running thousands of concurrent microVMs, keeping full memory files mapped causes severe memory overcommitment, disk I/O contention, and cache thrashing.

### Method 2: Lazy Paging via Userfaultfd (The Trap)
- **What is Userfaultfd (UFFD)?** A Linux kernel feature (`userfaultfd(2)`) that allows user-space programs to intercept and handle page faults instead of the kernel.
- **Mechanism:** Firecracker starts the microVM with zero memory preloaded. When the guest CPU attempts to read a memory address, the CPU halts, the kernel sends a fault notification over a UNIX socket to a userspace handler daemon (`uffd_handler`), the daemon reads that 4 KB page from disk/network, injects it via `ioctl(UFFDIO_COPY)`, and unpauses the vCPU.
- **The Bottleneck:** While the microVM appears to boot instantly, its initial execution crawls (**~103.1 ms, a 148% slowdown!**). Every unmapped page triggers an in-kernel trap and user-space context switch ("page fault storm").

### Method 3: REAP (Record and Prefetch) — The Solution
Introduced in the seminal ASPLOS '21 paper (*"Benchmarking, Analysis, and Optimization of Serverless Function Snapshots"*), **REAP** is based on a key architectural insight:
> **Serverless functions exhibit deterministic memory access patterns during cold start.** A function accesses almost the exact same subset of memory pages (its "working set") every time it is invoked.

REAP operates in two phases:
1. **Record Phase:** Run the function once using a recording handler (`uffd_handler_record`). Every time a page fault occurs, log its memory address to `working_set_offsets.txt`.
2. **Prefetch Phase:** When restoring subsequent instances of that function, a prefetch handler (`uffd_handler_reap`) reads `working_set_offsets.txt` and eagerly pushes all those pages into guest RAM via bulk `UFFDIO_COPY` *before* resuming the guest.

---

## 📊 Empirical Results (Real Testbed Data)

The measurements below were gathered on an Ubuntu 24.04 LTS host running Firecracker v1.17.0 over 30 repeated trials per technique (available in [`results.csv`](results.csv)):

| Restoration Technique | Trials | Mean Latency | Median Latency | Min Latency | Max Latency | P95 Tail Latency | Std Deviation | Working Set / Prefetch |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **File-backed Snapshot** | 30 | **41.49 ms** | 42.17 ms | 32.48 ms | 44.58 ms | **44.31 ms** | 2.72 ms | N/A (Host kernel page cache) |
| **Lazy UFFD (Demand Paging)** | 30 | **103.07 ms** | 114.95 ms | 63.22 ms | 123.57 ms | **122.31 ms** | 20.14 ms | 0 pages (On-demand traps) |
| **REAP (Record & Prefetch)** | 30 | **79.37 ms** | 91.61 ms | 48.21 ms | 95.66 ms | **95.41 ms** | 19.22 ms | **2,024 pages (7.906 MiB in 3.428 ms)** |

### Detailed Analysis of Results:
1. **The Lazy Paging Cost (+61.6 ms):** Lazy UFFD takes a mean of **103.07 ms** (and P95 of **122.31 ms**). The repetitive round-trip traps between KVM, the Linux kernel, and the userspace UFFD socket add tens of milliseconds of overhead.
2. **REAP Speedup (-23.7 ms):** In record mode, our test workload accessed exactly **2,024 unique pages (7.906 MiB)** out of its 512 MiB total allocated RAM (only **1.54%** of the guest's memory!).
3. **Sub-4ms Prefetch:** The REAP handler prefetched all 2,024 pages in just **3.428 ms** (`PREFETCH_COMPLETE pages=2024 elapsed_ms=3.428`). This eliminated invocation page faults and reduced mean latency from 103.07 ms down to **79.37 ms** (a **23.0% speedup**), reducing P95 tail latency by **26.9 ms** down to **95.41 ms**.
4. **Snapshot Baseline:** File-backed snapshots achieved **41.49 ms** with very low jitter (StdDev = 2.72 ms) because memory faults are resolved directly inside host kernel space without socket IPC.

---

## 🔬 How Everything Was Built & Evaluated

The research progressed chronologically across several stages:

### Step 1: Environment & Guest Workload Setup
- **Host:** Ubuntu 24.04 LTS (Kernel 6.18.56+ x86_64, GenuineIntel CPU).
- **Hypervisor:** Firecracker v1.17.0.
- **Guest VM:** Minimized Ubuntu 24.04.5 LTS image (1 vCPU, 512 MiB RAM) configured with:
  - Kernel: `vmlinux`
  - Boot args: `console=ttyS0 reboot=k panic=1 pci=off root=/dev/vda rw`
- **Guest Runner ([`runner.sh`](runner.sh)):** A shell script running inside the guest on `/dev/ttyS0`. Upon boot, it outputs `RUNNER_READY` and listens for commands:
  - `PING` $\rightarrow$ responds with `PONG` (used to verify microVM readiness).
  - `RUN hello <id>` $\rightarrow$ executes workload, outputs start/complete markers:
    ```
    BENCHMARK_STARTED id=<id> function=hello
    FUNCTION_START
    Hello World from Firecracker!
    BENCHMARK_COMPLETE
    BENCHMARK_COMPLETE id=<id> status=OK
    ```

### Step 2: Snapshot Creation
With the microVM booted and the guest runner idle:
1. Paused the microVM via the Firecracker REST API:
   ```bash
   curl --unix-socket /tmp/fc-benchmark.socket -X PATCH http://localhost/vm -d '{"state":"Paused"}'
   ```
2. Created a full snapshot:
   ```bash
   curl --unix-socket /tmp/fc-benchmark.socket -X PUT http://localhost/snapshot/create -d '{
     "snapshot_type": "Full",
     "snapshot_path": "/home/.../snapshots/benchmark/vm_state",
     "mem_file_path": "/home/.../snapshots/benchmark/vm_memory"
   }'
   ```
3. Backed up root filesystem: `cp rootfs/vm2.ext4 snapshots/benchmark/rootfs_snapshot.ext4` (1.0 GB).

### Step 3: From Naive Prototype to Synchronized Benchmarking
- **Phase 1 ([`benchmark_original.py`](benchmark_original.py)):** Initial single-trial prototype. It used an arbitrary `time.sleep(0.05)` after unpausing the VM to allow the serial listener to wake up. This hardcoded sleep skewed latency to **89.975 ms** and lumped VM restore time together with function execution.
- **Phase 2 ([`benchmark_snapshot.py`](benchmark_snapshot.py)):** Replaced the sleep with an active bidirectional handshake:
  ```python
  os.write(master, b"PING\r")
  ready = read_until(master, "PONG")
  ```
  This cleanly decoupled hypervisor restore time (`ready_ms`) from function invocation time (`invocation_ms`), while automating 30 consecutive trials with atomic disk resets (`shutil.copyfile`).
- **Phase 3 ([`analyze_snapshot.py`](analyze_snapshot.py)):** Computes statistical metrics across trials (Mean, Median, StdDev, Min/Max, and P95 rank-order percentiles).

### Step 4: The REAP Evaluation Harness ([`benchmark_uffd.py`](benchmark_uffd.py))
To evaluate REAP against lazy paging, we built a unified harness supporting three operational modes:
1. **Record Mode (`--mode record`):** Runs `bin/uffd_handler_record`. During VM restore and function execution, the handler logs accessed page offsets into `record_001.log`. We then extract unique offsets into `working_set_offsets.txt` (2,024 pages / 7.906 MiB).
2. **Lazy Mode (`--mode uffd`):** Runs `bin/uffd_handler`. The microVM starts with 0 pages loaded and handles faults on demand, measuring baseline lazy paging overhead.
3. **REAP Mode (`--mode reap`):** Passes `REAP_OFFSETS=working_set_offsets.txt` to `bin/uffd_handler_reap`. The harness waits for `PREFETCH_COMPLETE pages=2024 elapsed_ms=...` before sending `PATCH /vm {"state":"Resumed"}`.

### Step 5: Memory Scanning Workload ([`memrunner.c`](memrunner.c))
To stress the memory subsystem beyond basic `hello` execution, we implemented a static C binary that allocates configurable chunks of RAM (e.g., 64 MB) and touches every 4 KB page to evaluate page-fault behavior under heavy working-set memory pressure.

---

## 📂 Repository File Guide

| File | Purpose |
| :--- | :--- |
| [`benchmark_original.py`](benchmark_original.py) | Initial single-trial snapshot restore prototype (showcasing the arbitrary sleep limitation). |
| [`benchmark_snapshot.py`](benchmark_snapshot.py) | Robust 30-trial benchmark using active `PING/PONG` serial synchronization and disk resets. |
| [`benchmark_uffd.py`](benchmark_uffd.py) | Unified research harness supporting `--mode record`, `--mode uffd`, and `--mode reap`. |
| [`analyze_snapshot.py`](analyze_snapshot.py) | Statistical processing script computing Mean, Median, Min, Max, StdDev, and P95 latency. |
| [`results.csv`](results.csv) | Full empirical dataset containing latency numbers for all 90 benchmark trials. |
| [`runner.sh`](runner.sh) | Guest-side execution script running inside the Ubuntu microVM (`/root/benchmarks/runner.sh`). |
| [`memrunner.c`](memrunner.c) | Static C benchmark for memory scanning and footprint stress testing. |
| [`generate_report.py`](generate_report.py) | Python script using ReportLab and Matplotlib to compile the research report PDF locally. |

---

## 🚀 How to Run the Benchmarks

### Requirements (Linux with KVM)
- Host Linux kernel 5.4+ with `KVM` and `userfaultfd` enabled.
- `firecracker` binary installed in your `$PATH`.
- Python 3.8+ with `curl`.

### Execution Commands

```bash
# 1. Run 30 trials of standard file-backed snapshot restoration
python3 benchmark_snapshot.py

# 2. View statistical analysis (Mean, Median, P95, StdDev)
python3 analyze_snapshot.py

# 3. Record working-set pages during a cold start invocation
python3 benchmark_uffd.py --mode record --trials 1

# 4. Run 30 trials of REAP prefetch restoration
python3 benchmark_uffd.py --mode reap --trials 30

# 5. Run 30 trials of Lazy Demand-Paging UFFD baseline
python3 benchmark_uffd.py --mode uffd --trials 30

# 6. Generate the publication PDF report with updated plots
python3 generate_report.py
```

---

## 📚 References
- Dmitrii Ustiugov et al., *"Benchmarking, Analysis, and Optimization of Serverless Function Snapshots"*, ASPLOS 2021.
- AWS Firecracker: [https://firecracker-microvm.github.io/](https://firecracker-microvm.github.io/)
- Linux userfaultfd documentation: `man 2 userfaultfd`
