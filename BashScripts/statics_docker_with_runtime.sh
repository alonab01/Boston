#!/bin/bash
set -euo pipefail

# -----------------------------
# Config
# -----------------------------
IMAGE="alonab01/ignite_pc:latest"
RUNTIME="${RUNTIME:-runc}"   # override via env


C_A="cta"
C_B="ctb"

ITER="${ITER:-1000}"
OUT_DIR="${OUT_DIR:-results/out}"
mkdir -p "$OUT_DIR"

TARGET_FILE="/bin/whoami"
TARGET_PAGE_RANGE="0"

# -----------------------------
# Helpers
# -----------------------------
die() { echo "ERROR: $*" >&2; exit 1; }

check_runtime_exists() {
  local rt="$1"
  docker info 2>/dev/null | grep -q "Runtimes:.*\b$rt\b" || \
    die "Docker runtime '$rt' not found. Run: docker info | sed -n '/Runtimes:/,/Default Runtime/p'"
}

drop_caches_host() {
  sync
  echo 1 | sudo tee /proc/sys/vm/drop_caches >/dev/null
  sleep 0.1
}

rm_containers() {
  docker rm -f "$C_A" "$C_B" >/dev/null 2>&1 || true
}

start_containers() {
  # keep containers alive so we can exec
  docker run -d --name "$C_A" \
    --runtime "$RUNTIME" \
    "$IMAGE" sleep infinity >/dev/null

  docker run -d --name "$C_B" \
    --runtime "$RUNTIME" \
    "$IMAGE" sleep infinity >/dev/null
}

ct_cmd() {
  local c="$1"; shift
  docker exec -i "$c" sh -lc "$*"
}

read_page_container() {
  local c="$1"
  ct_cmd "$c" "/usr/local/bin/read_page '$TARGET_FILE' -m -p '$TARGET_PAGE_RANGE'"
}

append_stats() {
  local file="$1"
  awk -F, '
    $1 ~ /^[0-9]+$/ { x=$2; n++; sum+=x; sumsq+=x*x }
    END {
      if (n>0) {
        mean=sum/n
        std=sqrt((sumsq/n)-(mean*mean))
        printf "SUMMARY,COUNT=%d,MEAN=%.2f,STD=%.2f\n", n, mean, std
      }
    }
  ' "$file" >> "$file"
}

cleanup() { rm_containers; }
trap cleanup EXIT INT TERM

# -----------------------------
# Main
# -----------------------------
# check_runtime_exists "$RUNTIME"

echo "Docker runtime: $RUNTIME"
echo "Image: $IMAGE"
echo "Target: $TARGET_FILE  page-range: $TARGET_PAGE_RANGE"
echo "Iterations: $ITER"
echo

# -----------------------------
# Section 1: A reads (fresh env each iteration)
# -----------------------------
echo "Section 1: A reads (fresh containers each iteration)"
F1="$OUT_DIR/section1_A_fresh_${RUNTIME}.csv"
: > "$F1"

for i in $(seq 1 "$ITER"); do
  rm_containers
  drop_caches_host
  start_containers

  read_page_container "$C_A" >> "$F1"
done

append_stats "$F1"

# -----------------------------
# Section 2: B reads then A reads (fresh env each iteration)
# -----------------------------
echo "Section 2: B reads then A reads (fresh containers each iteration)"
F2="$OUT_DIR/section2_BA_fresh_${RUNTIME}.csv"
: > "$F2"

for i in $(seq 1 "$ITER"); do
  rm_containers
  drop_caches_host
  start_containers

  read_page_container "$C_B" > /dev/null
  read_page_container "$C_A" >> "$F2"
done

append_stats "$F2"

echo "Done. Outputs in: $OUT_DIR"
