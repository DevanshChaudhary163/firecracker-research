
#!/usr/bin/env python3

import argparse
import csv
import json
import os
import pty
import re
import select
import shutil
import subprocess
import time
from pathlib import Path

BASE = Path("/home/devansh-chaudhary/firecracker-research")
SNAP = BASE / "snapshots/benchmark"
RESULTS = BASE / "results/benchmarks"
REAP = BASE / "results/reap/benchmark"

ROOTFS = BASE / "rootfs/vm2.ext4"
SOCK = "/tmp/fc-reap-bench.socket"
UFFD_SOCK = "/tmp/fc-reap-handler.sock"

HANDLERS = {
    "record": BASE / "bin/uffd_handler_record",
    "uffd": BASE / "bin/uffd_handler",
    "reap": BASE / "bin/uffd_handler_reap",
}

def now():
    return time.perf_counter_ns()

def api(method, endpoint, body):
    subprocess.run(
        [
            "curl", "-fsS",
            "--unix-socket", SOCK,
            "-X", method,
            "http://localhost" + endpoint,
            "-H", "Content-Type: application/json",
            "-d", json.dumps(body),
        ],
        check=True,
        timeout=15,
    )

def wait_for_socket(path, process, timeout=10):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Process exited: {process.returncode}"
            )

        if Path(path).is_socket():
            return

        time.sleep(0.001)

    raise TimeoutError(f"Socket not ready: {path}")

def read_until(fd, marker, timeout=15):
    deadline = time.monotonic() + timeout
    output = bytearray()
    target = marker.encode()

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()

        readable, _, _ = select.select(
            [fd], [], [], min(remaining, 0.05)
        )

        if not readable:
            continue

        data = os.read(fd, 4096)

        if not data:
            raise RuntimeError("Serial console closed")

        output.extend(data)

        if target in output:
            return now()

        if len(output) > 65536:
            output = output[-32768:]

    raise TimeoutError(f"Missing guest marker: {marker}")

def wait_for_prefetch(log_path, process, timeout=20):
    deadline = time.monotonic() + timeout
    pattern = re.compile(
        r"PREFETCH_COMPLETE pages=(\d+) elapsed_ms=([\d.]+)"
    )

    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"REAP handler exited; inspect {log_path}"
            )

        contents = log_path.read_text(errors="replace")
        match = pattern.search(contents)

        if match:
            return int(match.group(1)), float(match.group(2))

        time.sleep(0.002)

    raise TimeoutError(
        f"Prefetch did not complete; inspect {log_path}"
    )

def run_trial(mode, trial):
    # The baseline also resets the disk before its timer.
    shutil.copyfile(SNAP / "rootfs_snapshot.ext4", ROOTFS)

    for path in (SOCK, UFFD_SOCK):
        if os.path.lexists(path):
            raise RuntimeError(
                f"Existing socket {path}; check for old processes"
            )

    log_path = REAP / f"{mode}_{trial:03d}.log"

    master, slave = pty.openpty()
    fc = None
    handler = None

    env = os.environ.copy()

    if mode == "reap":
        env["REAP_OFFSETS"] = str(
            REAP / "working_set_offsets.txt"
        )

    try:
        with log_path.open("w") as log:
            start = now()

            handler = subprocess.Popen(
                [
                    str(HANDLERS[mode]),
                    UFFD_SOCK,
                    str(SNAP / "vm_memory"),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
            )

            wait_for_socket(UFFD_SOCK, handler)

            fc = subprocess.Popen(
                ["firecracker", "--api-sock", SOCK],
                stdin=slave,
                stdout=slave,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            os.close(slave)
            slave = -1

            wait_for_socket(SOCK, fc)

            api("PUT", "/snapshot/load", {
                "snapshot_path": str(SNAP / "vm_state"),
                "mem_backend": {
                    "backend_type": "Uffd",
                    "backend_path": UFFD_SOCK,
                },
                "resume_vm": False,
            })

            pages = 0
            prefetch_ms = 0.0

            if mode == "reap":
                pages, prefetch_ms = wait_for_prefetch(
                    log_path, handler
                )

            api("PATCH", "/vm", {"state": "Resumed"})

            os.write(master, b"PING\r")
            ready = read_until(master, "PONG")

            command = f"RUN hello {trial}\r"
            os.write(master, command.encode())

            marker = (
                f"BENCHMARK_COMPLETE "
                f"id={trial} status=OK"
            )

            complete = read_until(master, marker)

            return {
                "trial": trial,
                "method": mode,
                "function": "hello",
                "total_ms": round(
                    (complete - start) / 1e6, 3
                ),
                "ready_ms": round(
                    (ready - start) / 1e6, 3
                ),
                "invocation_ms": round(
                    (complete - ready) / 1e6, 3
                ),
                "prefetch_ms": prefetch_ms,
                "prefetched_pages": pages,
            }

    finally:
        for proc in (fc, handler):
            if proc is not None:
                if proc.poll() is None:
                    proc.terminate()

                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

        os.close(master)

        if slave != -1:
            os.close(slave)

        # Remove only sockets owned by this finished trial.
        for path, proc in (
            (SOCK, fc),
            (UFFD_SOCK, handler),
        ):
            if proc is not None and proc.poll() is not None:
                if os.path.lexists(path):
                    os.unlink(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["record", "uffd", "reap"],
        required=True,
    )
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args()

    if args.trials < 1:
        parser.error("--trials must be >= 1")

    RESULTS.mkdir(parents=True, exist_ok=True)
    REAP.mkdir(parents=True, exist_ok=True)

    csv_path = RESULTS / f"{args.mode}.csv"

    columns = [
        "trial", "method", "function",
        "total_ms", "ready_ms", "invocation_ms",
        "prefetch_ms", "prefetched_pages",
    ]

    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for i in range(1, args.trials + 1):
            result = run_trial(args.mode, i)
            writer.writerow(result)
            f.flush()

            print(
                f"{args.mode.upper()} "
                f"Trial {i:02d}: "
                f"{result['total_ms']:.3f} ms",
                flush=True,
            )

    print(f"Results saved: {csv_path}")

if __name__ == "__main__":
    main()
