#!/usr/bin/env python3

import os
import pty
import time
import select
import subprocess
from pathlib import Path

BASE = Path("/home/devansh-chaudhary/firecracker-research")

SOCK = "/tmp/fc-benchmark-python.socket"

SNAPSHOT = BASE / "snapshots/benchmark/vm_state"
MEMORY = BASE / "snapshots/benchmark/vm_memory"
ROOTFS_BACKUP = BASE / "snapshots/benchmark/rootfs_snapshot.ext4"
ROOTFS = BASE / "rootfs/vm2.ext4"

REQUEST_ID = "1"


def api(method, endpoint, data):
    import json

    command = [
        "curl",
        "--silent",
        "--show-error",
        "--fail-with-body",
        "--unix-socket",
        SOCK,
        "-X",
        method,
        f"http://localhost{endpoint}",
        "-H",
        "Content-Type: application/json",
        "-d",
        json.dumps(data),
    ]

    subprocess.run(command, check=True)


def wait_for_socket(timeout=5):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if os.path.exists(SOCK):
            return
        time.sleep(0.01)

    raise TimeoutError("Firecracker API socket not ready")


def read_until(fd, marker, timeout=10):
    deadline = time.monotonic() + timeout
    output = bytearray()

    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()

        readable, _, _ = select.select(
            [fd], [], [], min(remaining, 0.1)
        )

        if not readable:
            continue

        try:
            data = os.read(fd, 4096)
        except OSError as exc:
            raise RuntimeError("Serial console disconnected") from exc

        if not data:
            raise RuntimeError("Firecracker console closed")

        output.extend(data)

        print(data.decode(errors="replace"), end="", flush=True)

        if marker.encode() in output:
            return time.perf_counter_ns()

        if len(output) > 65536:
            output = output[-32768:]

    raise TimeoutError(f"Did not receive: {marker}")


def main():
    if os.path.exists(SOCK):
        raise RuntimeError(
            f"{SOCK} already exists. "
            "Stop its Firecracker process before retrying."
        )

    # Restore the exact disk state associated with the snapshot.
    subprocess.run(
        ["cp", str(ROOTFS_BACKUP), str(ROOTFS)],
        check=True
    )

    master, slave = pty.openpty()

    start = time.perf_counter_ns()

    process = subprocess.Popen(
        ["firecracker", "--api-sock", SOCK],
        stdin=slave,
        stdout=slave,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    os.close(slave)

    try:
        wait_for_socket()

        api(
            "PUT",
            "/snapshot/load",
            {
                "snapshot_path": str(SNAPSHOT),
                "mem_backend": {
                    "backend_type": "File",
                    "backend_path": str(MEMORY),
                },
                "resume_vm": False,
            },
        )

        api(
            "PATCH",
            "/vm",
            {"state": "Resumed"},
        )

        # Allow the restored serial listener to resume.
        time.sleep(0.05)

        command = f"RUN hello {REQUEST_ID}\r"

        os.write(master, command.encode())

        marker = (
            f"BENCHMARK_COMPLETE "
            f"id={REQUEST_ID} status=OK"
        )

        end = read_until(master, marker)

        elapsed_ms = (end - start) / 1_000_000

        print()
        print("=" * 45)
        print(f"Method: Snapshot restoration")
        print(f"Function: Hello World")
        print(f"Total latency: {elapsed_ms:.3f} ms")
        print("=" * 45)

    finally:
        process.terminate()

        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

        os.close(master)

        if os.path.exists(SOCK):
            os.unlink(SOCK)


if __name__ == "__main__":
    main()	
