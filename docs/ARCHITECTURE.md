# Architecture & Technical Methodology

This document outlines the system architecture and memory management mechanics used in this research.

---

## System Architecture

```mermaid
flowchart TD
    BenchHarness["Benchmark Harness (Python)"]
    Firecracker["Firecracker Hypervisor (KVM)"]
    UffdHandler["UFFD Handler (Record / Lazy / REAP)"]
    GuestVM["Guest MicroVM (Linux Kernel + Workload)"]

    BenchHarness -->|API REST / PUT /snapshot/load| Firecracker
    BenchHarness -->|PTY Serial Console / PING - RUN| GuestVM
    Firecracker <-->|Unix Domain Socket| UffdHandler
    GuestVM -->|KVM EPT / Page Fault Traps| Firecracker
    UffdHandler -->|UFFDIO_COPY / Prefetched Pages| Firecracker
```

---

## Memory Management Paradigms

| Strategy | Memory Backend | Cold Start Mechanics | Trade-offs |
| :--- | :--- | :--- | :--- |
| **File-backed Snapshot** | `File` (`vm_memory`) | Backed by file on host filesystem. Linux kernel demand-pages on access. | Fast startup, but consumes large host disk bandwidth and RAM across multi-tenant instances. |
| **Lazy UFFD** | `Uffd` (`/tmp/fc-reap-handler.sock`) | Zero pages loaded upfront. Page faults trap to userspace UFFD daemon. | Instant microVM startup, but severe execution penalty (+548% latency) due to context switches. |
| **REAP (Record & Prefetch)** | `Uffd` (`/tmp/fc-reap-handler.sock`) | **Phase 1 (Record):** Log accessed pages to `working_set_offsets.txt`.<br/>**Phase 2 (Prefetch):** Issue bulk `UFFDIO_COPY` calls before resuming the guest. | Eliminates page-fault storms during invocation while retaining low baseline memory footprint. |

---

## Synchronization Protocol (Active Handshake)

To eliminate timing jitter caused by arbitrary sleep delays, the benchmark harness enforces a strict serial synchronization protocol:

```mermaid
sequenceDiagram
    participant H as Benchmark Harness
    participant FC as Firecracker API
    participant G as Guest MicroVM Console

    H->>FC: PUT /snapshot/load (Uffd / File)
    H->>FC: PATCH /vm {"state": "Resumed"}
    H->>G: Write "PING\r"
    G-->>H: Match "PONG" (ready_ms recorded)
    H->>G: Write "RUN hello {trial}\r"
    G-->>H: Match "BENCHMARK_COMPLETE id={trial} status=OK"
    Note over H,G: invocation_ms = complete - ready_ms
```
