#!/usr/bin/env python3

import os
import csv
import json
import pty
import select
import shutil
import subprocess
import time

from pathlib import Path

BASE = Path("/home/devansh-chaudhary/firecracker-research")

SOCK = "/tmp/fc-benchmark-python.socket"

SNAPSHOT = BASE / "snapshots/benchmark/vm_state"
MEMORY = BASE / "snapshots/benchmark/vm_memory"

ROOTFS_BACKUP = BASE / "snapshots/benchmark/rootfs_snapshot.ext4"
ROOTFS = BASE / "rootfs/vm2.ext4"

RESULTS = BASE / "results/benchmarks/snapshot.csv"

TRIALS = 30


def now():
    return time.perf_counter_ns()


def api(method, endpoint, data):

    command = [
        "curl",
        "--silent",
        "--show-error",
        "--fail-with-body",
        "--unix-socket", SOCK,
        "-X", method,
        f"http://localhost{endpoint}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(data),
    ]

    subprocess.run(command, check=True, timeout=10)


def wait_for_socket(timeout=5):

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        if os.path.exists(SOCK):
            return

        time.sleep(0.001)

    raise TimeoutError("Firecracker API socket not ready")


def read_until(fd, marker, timeout=10):

    deadline = time.monotonic() + timeout
    output = bytearray()

    while time.monotonic() < deadline:

        readable, _, _ = select.select(
            [fd], [], [], 0.01
        )

        if not readable:
            continue

        try:
            data = os.read(fd, 4096)
        except OSError as exc:
            raise RuntimeError(
                "Serial console disconnected"
            ) from exc

        if not data:
            raise RuntimeError("Serial console closed")

        output.extend(data)

        if marker.encode() in output:
            return now()

        if len(output) > 65536:
            output = output[-32768:]

    raise TimeoutError(f"Marker not received: {marker}")


def run_trial(trial):

    # Each trial starts from the same disk state.
    shutil.copyfile(ROOTFS_BACKUP, ROOTFS)

    if os.path.exists(SOCK):
        raise RuntimeError(
            f"Socket already exists: {SOCK}"
        )

    master, slave = pty.openpty()
    process = None

    try:

        start = now()

        process = subprocess.Popen(
            ["firecracker", "--api-sock", SOCK],
            stdin=slave,
            stdout=slave,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        os.close(slave)
        slave = -1

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

        # Check that the runner accepts commands.
        os.write(master, b"PING\r")

        ready = read_until(
            master,
            "PONG",
            timeout=10,
        )

        # Execute the benchmark function.
        request_id = str(trial)

        command = f"RUN hello {request_id}\r"
        os.write(master, command.encode())

        marker = (
            f"BENCHMARK_COMPLETE "
            f"id={request_id} status=OK"
        )

        complete = read_until(
            master,
            marker,
            timeout=10,
        )

        total_ms = (complete - start) / 1_000_000

        startup_ms = (ready - start) / 1_000_000

        invocation_ms = (complete - ready) / 1_000_000

        return {
            "trial": trial,
            "method": "snapshot",
            "function": "hello",
            "total_ms": round(total_ms, 3),
            "ready_ms": round(startup_ms, 3),
            "invocation_ms": round(invocation_ms, 3),
        }

    finally:

        if process is not None:

            if process.poll() is None:
                process.terminate()

            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        os.close(master)

        if slave != -1:
            os.close(slave)

        # Only remove the socket after our process exits.
        if process is not None and process.poll() is not None:
            if os.path.exists(SOCK):
                os.unlink(SOCK)


def main():

    RESULTS.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "trial",
        "method",
        "function",
        "total_ms",
        "ready_ms",
        "invocation_ms",
    ]

    with RESULTS.open("w", newline="") as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for trial in range(1, TRIALS + 1):

            try:

                result = run_trial(trial)

                writer.writerow(result)
                file.flush()

                print(
                    f"Trial {trial:02d}: "
                    f"{result['total_ms']:.3f} ms"
                )

            except Exception as exc:

                print(f"Trial {trial:02d} FAILED: {exc}")
                raise

    print()
    print("Benchmark completed.")
    print(f"Results saved to: {RESULTS}")


if __name__ == "__main__":
    main()
