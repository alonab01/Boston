#!/bin/bash
set -euo pipefail

VM_PATH="/home/alonab01/vms"
USER="alonab01"
TARGET_FILE="/boot/initrd.img-6.8.0-90-generic"
TARGET_PAGE_RANGE="4-10"
SSH_OPTS="-T -q -o LogLevel=ERROR -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

mkdir -p out

echo "Starting two VMs (vmA and vmB)..."

qemu-system-x86_64 -enable-kvm -m 2048 \
  -drive file="$VM_PATH/vmA.qcow2",if=virtio \
  -boot c \
  -nic user,hostfwd=tcp:127.0.0.1:2222-:22 >/dev/null 2>&1 &

qemu-system-x86_64 -enable-kvm -m 2048 \
  -drive file="$VM_PATH/base.qcow2",if=virtio \
  -boot c \
  -nic user,hostfwd=tcp:127.0.0.1:2223-:22 >/dev/null 2>&1 &

sleep 45

drop_caches_host() {
  sync
  echo 1 | sudo tee /proc/sys/vm/drop_caches >/dev/null
  sleep 0.1
}

drop_caches_vm() {
  local port="$1"
  ssh $SSH_OPTS -p "$port" "$USER@localhost" \
    " echo 1 | sudo tee /proc/sys/vm/drop_caches >/dev/null" 2>/dev/null
    sleep 0.1
}

read_page_vm() {
  local port="$1"
  ssh $SSH_OPTS -p "$port" "$USER@localhost" \
    "cd ~/Documents/Boston && ./read_page '$TARGET_FILE' -m -p '$TARGET_PAGE_RANGE'" 2>/dev/null
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


# Make sure both VMs start from cold-ish cache
drop_caches_vm 2222
drop_caches_vm 2223
drop_caches_host

echo "Section 1: vmA reads from disk (host cache dropped each round)"
: > out/section1_vmA.csv
for i in {1..30}; do
  read_page_vm 2222 >> out/section1_vmA.csv
  drop_caches_vm 2222
  drop_caches_host
done

append_stats out/section1_vmA.csv



echo "Section 2: vmB reads then vmA reads (host cache dropped before vmB)"
: > out/section2_vmB_vmA.csv
for i in {1..30}; do
  drop_caches_host
  read_page_vm 2223 > /dev/null
  read_page_vm 2222 >> out/section2_vmB_vmA.csv
  drop_caches_vm 2223
  drop_caches_vm 2222
  drop_caches_host
done

append_stats out/section2_vmB_vmA.csv

# shutdown (non-interactive sudo)
# ssh $SSH_OPTS -p 2222 "$USER@localhost" "sudo -n poweroff" 2>/dev/null || true
# ssh $SSH_OPTS -p 2223 "$USER@localhost" "sudo -n poweroff" 2>/dev/null || true
