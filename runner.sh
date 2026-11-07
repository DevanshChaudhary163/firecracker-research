#!/bin/bash
# Guest benchmark runner executed inside Ubuntu microVM console (/root/benchmarks/runner.sh)
echo "RUNNER_READY"

while read -r line; do
  cmd=$(echo "$line" | tr -d '\r')
  if [ "$cmd" = "PING" ]; then
    echo "PONG"
  elif [[ "$cmd" =~ ^RUN\ ([a-zA-Z0-9_-]+)\ ([0-9]+)$ ]]; then
    fn="${BASH_REMATCH[1]}"
    id="${BASH_REMATCH[2]}"
    echo "BENCHMARK_STARTED id=$id function=$fn"
    echo "FUNCTION_START"
    echo "Hello World from Firecracker!"
    echo "BENCHMARK_COMPLETE"
    echo "BENCHMARK_COMPLETE id=$id status=OK"
  fi
done
