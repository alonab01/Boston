#!/bin/bash
set -euo pipefail

# -----------------------------
# Defaults
# -----------------------------
RUNTIME="docker"          # ignite | docker
DOCKER_RUNTIME="runsc-systrap"         # empty = docker default, or set to runc/runsc/kata/...
IMAGE="alonab01/ignite_pc:latest"

VM_A="vma"
VM_B="vmb"
C_A="cta"
C_B="ctb"

CPUS="1"
MEMORY_IGNITE="2GB"
MEMORY_DOCKER="2g"
DISK_SIZE="10GB"

# TARGET_FILE="/boot/vmlinux-5.10.51"
TARGET_FILE="/bin/whoami"

TARGET_PAGE_RANGE="0"

OUT_DIR="results/out"
mkdir -p "$OUT_DIR"
ITER=1000

# Docker-only knobs
DOCKER_NO_NET=1
DOCKER_PRIVILEGED=1   # needed if you insist on echo > /proc/sys/vm/drop_caches inside container


# -----------------------------
# Common helpers
# -----------------------------
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

drop_caches_host() {
  sync
  echo 1 | sudo tee /proc/sys/vm/drop_caches >/dev/null
  sleep 0.1
  # sync
  # echo 1 | sudo tee /proc/sys/vm/drop_caches >/dev/null
  # sleep 0.1
}

# -----------------------------
# Ignite backend
# -----------------------------
ignite_clean() { sudo ignite rm -f "$VM_A" "$VM_B" >/dev/null 2>&1 || true; }

ignite_disable_motd_vm() {
  local vm="$1"
  sudo ignite ssh -t=false "$vm" <<'EOF'
rm -f /etc/motd
rm -rf /etc/update-motd.d/*
touch /etc/motd
EOF
}

ignite_vm_script() {
  local vm="$1"; shift
  sudo ignite ssh -t=false "$vm" <<EOF
set -e
$*
EOF
}

ignite_start_pair() {
  echo "Starting Ignite microVMs ($VM_A, $VM_B)..."
  ignite_clean
  sudo ignite run "$IMAGE" --name "$VM_A" --cpus "$CPUS" --memory "$MEMORY_IGNITE" --size "$DISK_SIZE" --ssh >/dev/null
  sudo ignite run "$IMAGE" --name "$VM_B" --cpus "$CPUS" --memory "$MEMORY_IGNITE" --size "$DISK_SIZE" --ssh >/dev/null
  sleep 10
  ignite_disable_motd_vm "$VM_A"
  ignite_disable_motd_vm "$VM_B"
}

ignite_stop_pair() {
  sudo ignite stop "$VM_A" "$VM_B" >/dev/null 2>&1 || true
  ignite_clean
}

ignite_drop_caches_guest() {
  local vm="$1"
  ignite_vm_script "$vm" "sync; echo 1 > /proc/sys/vm/drop_caches; sleep 0.1"
}

ignite_read_page_guest() {
  local vm="$1"
  ignite_vm_script "$vm" "/usr/local/bin/read_page '$TARGET_FILE' -m -p '$TARGET_PAGE_RANGE'"
}

# -----------------------------
# Docker backend (runtime-selectable)
# -----------------------------
docker_clean() { docker rm -f "$C_A" "$C_B" >/dev/null 2>&1 || true; }

docker_check_runtime_exists() {
  local rt="$1"
  [[ -z "$rt" ]] && return 0

  # Best-effort check; docker info prints "Runtimes: runc io.containerd.runc.v2 ..."
  if ! docker info 2>/dev/null | grep -q "Runtimes:.*\b$rt\b"; then
    echo "ERROR: Docker runtime '$rt' not found in 'docker info' runtimes." >&2
    echo "Run: docker info | sed -n '/Runtimes:/,/Default Runtime/p'" >&2
    exit 1
  fi
}

docker_start_pair() {
  echo "Starting Docker containers ($C_A, $C_B)..."
  docker_clean
  docker_check_runtime_exists "$DOCKER_RUNTIME"

  local net_args=()
  if [[ "$DOCKER_NO_NET" -eq 1 ]]; then net_args+=(--network none); fi

  local priv_args=()
  if [[ "$DOCKER_PRIVILEGED" -eq 1 ]]; then priv_args+=(--privileged); fi

  local rt_args=()
  if [[ -n "$DOCKER_RUNTIME" ]]; then rt_args+=(--runtime "$DOCKER_RUNTIME"); fi

  # Keep containers alive so we can exec repeatedly
  docker run -d --name "$C_A" \
    --cpus "$CPUS" --memory "$MEMORY_DOCKER" \
    "${rt_args[@]}" "${net_args[@]}" "${priv_args[@]}" \
    "$IMAGE" sleep infinity >/dev/null

  docker run -d --name "$C_B" \
    --cpus "$CPUS" --memory "$MEMORY_DOCKER" \
    "${rt_args[@]}" "${net_args[@]}" "${priv_args[@]}" \
    "$IMAGE" sleep infinity >/dev/null

  sleep 1
}

docker_stop_pair() { docker_clean; }

docker_cmd() {
  local c="$1"; shift
  docker exec -i "$c" sh -lc "$*"
}

docker_drop_caches_guest() {
  local c="$1"
  # NOTE: this needs privileged/caps; otherwise permission denied.
  docker_cmd "$c" "sync; echo 1 > /proc/sys/vm/drop_caches; sleep 0.1"
}

docker_read_page_guest() {
  local c="$1"
  docker_cmd "$c" "/usr/local/bin/read_page '$TARGET_FILE' -m -p '$TARGET_PAGE_RANGE'"
}

# -----------------------------
# Bind runtime to generic ops
# -----------------------------
if [[ "$RUNTIME" == "ignite" ]]; then
  start_pair() { ignite_start_pair; }
  stop_pair() { ignite_stop_pair; }
  drop_caches_guest() { ignite_drop_caches_guest "$1"; }
  read_page_guest() { ignite_read_page_guest "$1"; }
  GUEST_A="$VM_A"
  GUEST_B="$VM_B"
else
  start_pair() { docker_start_pair; }
  stop_pair() { docker_stop_pair; }
  drop_caches_guest() { docker_drop_caches_guest "$1"; }
  read_page_guest() { docker_read_page_guest "$1"; }
  GUEST_A="$C_A"
  GUEST_B="$C_B"
fi

# -----------------------------
# Experiment
# -----------------------------
run_phase() {
  local suffix="$1"

  drop_caches_guest "$GUEST_A"
  drop_caches_guest "$GUEST_B"
  drop_caches_host

  echo "Section 1 ($suffix): A reads (host cache dropped each round)"
  local f1="$OUT_DIR/section1_A_${suffix}_${RUNTIME}.csv"
  : > "$f1"
  for i in $(seq 1 "$ITER"); do
    read_page_guest "$GUEST_A" >> "$f1"
    drop_caches_guest "$GUEST_A"
    drop_caches_host
  done
  append_stats "$f1"

  echo "Section 2 ($suffix): B reads then A reads (host cache dropped before B)"
  local f2="$OUT_DIR/section2_BA_${suffix}_${RUNTIME}.csv"
  : > "$f2"
  for i in $(seq 1 "$ITER"); do
    drop_caches_host
    read_page_guest "$GUEST_B" > /dev/null
    read_page_guest "$GUEST_A" >> "$f2"
    drop_caches_guest "$GUEST_B"
    drop_caches_guest "$GUEST_A"
    drop_caches_host
  done
  append_stats "$f2"
}

echo "Runtime backend: $RUNTIME"
if [[ "$RUNTIME" == "docker" ]]; then
  echo "Docker runtime: ${DOCKER_RUNTIME:-<docker default>}"
fi

start_pair
run_phase "gvisor_systrap"
stop_pair

echo "Done. Outputs in: $OUT_DIR"
