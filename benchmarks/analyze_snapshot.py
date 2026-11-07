import csv
import statistics
from pathlib import Path

BASE = Path("/home/devansh-chaudhary/firecracker-research")

CSV_FILE = BASE / "results/benchmarks/snapshot.csv"

with CSV_FILE.open() as f:
    rows = list(csv.DictReader(f))

times = [float(row["total_ms"]) for row in rows]

times_sorted = sorted(times)

n = len(times_sorted)

p95_index = min(
    n - 1,
    max(0, (95 * n + 99) // 100 - 1),
)

print("\nSNAPSHOT RESTORATION BENCHMARK")
print("-" * 40)

print(f"Trials:       {n}")
print(f"Mean:         {statistics.mean(times):.3f} ms")
print(f"Median:       {statistics.median(times):.3f} ms")
print(f"Minimum:      {min(times):.3f} ms")
print(f"Maximum:      {max(times):.3f} ms")
print(f"Std deviation:{statistics.stdev(times):.3f} ms"
      if n > 1 else "Std deviation: N/A")
print(f"P95:          {times_sorted[p95_index]:.3f} ms")
