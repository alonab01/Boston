#!/bin/bash
set -euo pipefail

# ============================================================
# Config (override via env vars)
# ============================================================
IMAGE="${IMAGE:-docker.io/alonab01/ignite_pc:latest}"
RUNTIME="${RUNTIME:-io.containerd.kata.v2}"
SNAPSHOTTER="${SNAPSHOTTER:-devmapper}"
PLATFORM="${PLATFORM:-linux/amd64}"

ITER="${ITER:-1000}"
OUT_DIR="${OUT_DIR:-results/out}"
mkdir -p "$OUT_DIR"

TARGET_FILE="${TARGET_FILE:-/bin/whoami}"
TARGET_PAGE_RANGE="${TARGET_PAGE_RANGE:-0}"

# Make each run unique so we never collide with stale snapshots/containers
RUN_ID="${RUN_ID:-$(date +%Y%m%d_%H%M%S)}"

# If your read_page output is buffered, this helps the CSV update as it runs
USE_STDBUF="${USE_STDBUF:-1}"   # 1=yes, 0=no

# ctr wrapper (default namespace)
ctr() { sudo ctr "$@"; }

die() { echo "ERROR: $*" >&2; exit 1; }

# ============================================================
# Helpers
# ============================================================
drop_caches_host() {
  sync
  echo 1 | sudo tee /proc/sys/vm/drop_caches >/dev/null
  sleep 0.1
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

check_devmapper_ok() {
  if ! sudo ctr plugins ls | awk '$2=="devmapper" && $4=="ok"{found=1} END{exit !found}'; then
    echo "devmapper plugin line(s):"
    sudo ctr plugins ls | awk '$2=="devmapper"{print}'
    die "devmapper snapshotter must be ok."
  fi
}

ensure_image() {
  if ! ctr images ls -q | grep -qx "$IMAGE"; then
    echo "Containerd does not have image: $IMAGE"
    echo "Fix example:"
    echo "  docker save -o /tmp/ignite_pc.tar alonab01/ignite_pc:latest"
    echo "  sudo ctr images import /tmp/ignite_pc.tar"
    die "Image missing in containerd."
  fi
}

rm_container_one() {
  local name="$1"

  # kill task if running
  if ctr tasks ls 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$name"; then
    ctr tasks kill -s SIGKILL "$name" >/dev/null 2>&1 || true
    ctr tasks rm "$name" >/dev/null 2>&1 || true
  fi

  # remove container record if exists
  if ctr containers ls 2>/dev/null | awk 'NR>1{print $1}' | grep -qx "$name"; then
    ctr containers rm "$name" >/dev/null 2>&1 || true
  fi

  # best-effort remove snapshot key if ctr created it with the container name
  # (your ctr version supports "ctr snapshots delete <key>" without --snapshotter)
  ctr snapshots delete "$name" >/dev/null 2>&1 || true
}

cleanup_iteration() {
  local a="$1" b="$2"
  rm_container_one "$a"
  rm_container_one "$b"
}

start_containers() {
  local a="$1" b="$2"

  ctr run -d \
    --snapshotter "$SNAPSHOTTER" \
    --runtime "$RUNTIME" \
    --platform "$PLATFORM" \
    "$IMAGE" "$a" sleep infinity >/dev/null

  ctr run -d \
    --snapshotter "$SNAPSHOTTER" \
    --runtime "$RUNTIME" \
    --platform "$PLATFORM" \
    "$IMAGE" "$b" sleep infinity >/dev/null
}

ct_cmd() {
  local c="$1"; shift
  local cmd="$*"
  local exec_id="exec-$(date +%s%N)"
  ctr tasks exec -t --exec-id "$exec_id" "$c" sh -lc "$cmd"
}

read_page_container() {
  local c="$1"
  if [[ "$USE_STDBUF" == "1" ]]; then
    ct_cmd "$c" "stdbuf -oL -eL /usr/local/bin/read_page '$TARGET_FILE' -m -p '$TARGET_PAGE_RANGE'"
  else
    ct_cmd "$c" "/usr/local/bin/read_page '$TARGET_FILE' -m -p '$TARGET_PAGE_RANGE'"
  fi
}

# If user CTRL-C mid-run, try to kill leftover kata/firecracker too
cleanup_all() {
  # remove any of our per-iter containers that still exist
  # (best-effort: match RUN_ID)
  for c in $(ctr containers ls 2>/dev/null | awk 'NR>1{print $1}' | grep -E "^(cta|ctb)_${RUN_ID}_" || true); do
    rm_container_one "$c"
  done

  # best-effort kill stuck kata/firecracker shims from this run
  sudo pkill -f "firecracker.*(cta|ctb)_${RUN_ID}_" >/dev/null 2>&1 || true
  sudo pkill -f "containerd-shim-kata.*${RUN_ID}" >/dev/null 2>&1 || true
}
trap cleanup_all EXIT INT TERM

# ============================================================
# Main
# ============================================================
echo "snapshotter:   $SNAPSHOTTER"
echo "runtime:       $RUNTIME"
echo "platform:      $PLATFORM"
echo "image:         $IMAGE"
echo "target:        $TARGET_FILE  page-range: $TARGET_PAGE_RANGE"
echo "iterations:    $ITER"
echo "run_id:        $RUN_ID"
echo "live file:     USE_STDBUF=$USE_STDBUF"
echo

check_devmapper_ok
ensure_image

F1="$OUT_DIR/section1_A_fresh_ctr_${RUNTIME//\//_}_${RUN_ID}.csv"
F2="$OUT_DIR/section2_BA_fresh_ctr_${RUNTIME//\//_}_${RUN_ID}.csv"
: > "$F1"
: > "$F2"

# -----------------------------
# Section 1: A reads (fresh env each iteration)
# -----------------------------
echo "Section 1: A reads (fresh containers each iteration)"
for i in $(seq 1 "$ITER"); do
  C_A="cta_${RUN_ID}_${i}"
  C_B="ctb_${RUN_ID}_${i}"

  # ensure no collision (should not happen with unique names, but safe)
  cleanup_iteration "$C_A" "$C_B"

  drop_caches_host
  start_containers "$C_A" "$C_B"

  # append to file; should update continuously if stdbuf works
  read_page_container "$C_A" >> "$F1"

  # cleanup after each iteration to avoid accumulating devmapper usage
  cleanup_iteration "$C_A" "$C_B"
done
append_stats "$F1"

# -----------------------------
# Section 2: B reads then A reads (fresh env each iteration)
# -----------------------------
echo "Section 2: B reads then A reads (fresh containers each iteration)"
for i in $(seq 1 "$ITER"); do
  C_A="cta_${RUN_ID}_${i}"
  C_B="ctb_${RUN_ID}_${i}"

  cleanup_iteration "$C_A" "$C_B"

  drop_caches_host
  start_containers "$C_A" "$C_B"

  read_page_container "$C_B" >/dev/null
  read_page_container "$C_A" >> "$F2"

  cleanup_iteration "$C_A" "$C_B"
done
append_stats "$F2"

echo "Done."
echo "  $F1"
echo "  $F2"