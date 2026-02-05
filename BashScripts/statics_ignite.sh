#!/bin/bash
set -euo pipefail

# -----------------------------
# Config
# -----------------------------
IMAGE="alonab01/ignite_pc:latest"   # <-- change to your image name
VM_A="vma"
VM_B="vmb"

CPUS=1
MEMORY="2GB"
DISK_SIZE="10GB"       # adjust if you want; this is the VM disk size in Ignite

TARGET_FILE="/boot/vmlinux-5.10.51"
TARGET_PAGE_RANGE="0"

OUT_DIR="results/out"
mkdir -p "$OUT_DIR"

# -----------------------------
# Helpers
# -----------------------------


disable_motd_vm() {
  local vm="$1"
  sudo ignite ssh -t=false "$vm" <<'EOF'
# Completely disable Ubuntu MOTD spam
rm -f /etc/motd
rm -rf /etc/update-motd.d/*
touch /etc/motd
EOF
}


ignite_clean() {
  sudo ignite rm -f "$VM_A" "$VM_B" >/dev/null 2>&1 || true
}

start_vms() {
  echo "Starting two microVMs ($VM_A and $VM_B)..."
  ignite_clean

  sudo ignite run "$IMAGE" --name "$VM_A" --cpus "$CPUS" --memory "$MEMORY" --size "$DISK_SIZE" --ssh >/dev/null
  sudo ignite run "$IMAGE" --name "$VM_B" --cpus "$CPUS" --memory "$MEMORY" --size "$DISK_SIZE" --ssh >/dev/null

  # Wait a bit for SSH to be ready
  sleep 10

  # Disable MOTD spam (CRITICAL for clean logs)
  disable_motd_vm "$VM_A"
  disable_motd_vm "$VM_B"
}

stop_vms() {
  sudo ignite stop "$VM_A" "$VM_B" >/dev/null 2>&1 || true
  ignite_clean
}

# Run a script inside VM via stdin. IMPORTANT: -t=false for non-interactive.
vm_script() {
  local vm="$1"
  shift
  sudo ignite ssh -t=false "$vm" <<EOF
set -e
$*
EOF
}

drop_caches_host() {
  sync
  echo 1 | sudo tee /proc/sys/vm/drop_caches >/dev/null
  sleep 0.1 
}

drop_caches_vm() {
  local vm="$1"
  vm_script "$vm" "
sync
echo 1 > /proc/sys/vm/drop_caches
sleep 0.1
"
}

read_page_vm() {
  local vm="$1"
  # Assumes /usr/local/bin/read_page exists in your image
  vm_script "$vm" "
/usr/local/bin/read_page '$TARGET_FILE' -m -p '$TARGET_PAGE_RANGE'
"
}

append_stats() {
  local file="$1"

  awk -F, '
    $1 ~ /^[0-9]+$/ {
      x = $2
      n++
      sum += x
      sumsq += x*x
    }
    END {
      if (n > 0) {
        mean = sum / n
        std = sqrt((sumsq / n) - (mean * mean))
        printf "SUMMARY,COUNT=%d,MEAN=%.2f,STD=%.2f\n", n, mean, std
      }
    }
  ' "$file" >> "$file"
}

run_phase() {
  local suffix="$1"

  echo "Make sure both VMs start from cold-ish cache"
  drop_caches_vm "$VM_A"
  drop_caches_vm "$VM_B"
  drop_caches_host

  echo "Section 1 ($suffix): $VM_A reads (host cache dropped each round)"
  local f1="$OUT_DIR/section1_${VM_A}_${suffix}.csv"
  : > "$f1"

  for i in {1..1000}; do
    read_page_vm "$VM_A" >> "$f1"
    drop_caches_vm "$VM_A"
    drop_caches_host
  done
  append_stats "$f1"

  echo "Section 2 ($suffix): $VM_B reads then $VM_A reads (host cache dropped before $VM_B)"
  local f2="$OUT_DIR/section2_${VM_B}_${VM_A}_${suffix}.csv"
  : > "$f2"

  for i in {1..1000}; do
    drop_caches_host
    read_page_vm "$VM_B" > /dev/null
    read_page_vm "$VM_A" >> "$f2"
    drop_caches_vm "$VM_B"
    drop_caches_vm "$VM_A"
    drop_caches_host
  done
  append_stats "$f2"
}

# -----------------------------
# Main
# -----------------------------

# Phase 1
start_vms
run_phase "ignite2"
stop_vms

echo "Done. Outputs in: $OUT_DIR"