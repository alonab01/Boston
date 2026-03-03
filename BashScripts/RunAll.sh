#!/bin/bash
set -euo pipefail

# Order:
# 1) statics_diffrent_vms.sh (once)
# 2) statics_ignite.sh (once)
# 3) statics_docker_with_runtime.sh for:
#    runc, runsc-kvm, runsc-systrap,
#    io.containerd.kata.v2 twice:
#      - after: sudo kata-manager -S default
#      - after: sudo kata-manager -S clh

ITER_ALL=10000


# echo "[1/3] QEMU statistic"

# OUT_DIR=results/out/qemu_vms_wb CACHE_STATE=writeback ITER="$ITER_ALL" BashScripts/statics_diffrent_vms.sh
# sleep 100
# OUT_DIR=results/out/qemu_vms_none CACHE_STATE=none ITER="$ITER_ALL" BashScripts/statics_diffrent_vms.sh


# echo "[2/3] Ignite statistic"
# OUT_DIR=results/out/ignite ITER="$ITER_ALL" BashScripts/statics_ignite.sh

# echo "[3/3] Docker statistic per runtime"
# # runc
# OUT_DIR=results/out/docker ITER="$ITER_ALL" BashScripts/statics_docker_with_runtime.sh

# # # gVisor 
# OUT_DIR=results/out/gvisor_kvm  RUNTIME=runsc-kvm ITER="$ITER_ALL" BashScripts/statics_docker_with_runtime.sh

# OUT_DIR=results/out/gvisor_systrap  RUNTIME=runsc-systrap ITER="$ITER_ALL" BashScripts/statics_docker_with_runtime.sh

# # kata + QEMU
# sudo kata-manager -S default
# OUT_DIR=results/out/kata_qemu  RUNTIME=io.containerd.kata.v2 ITER="$ITER_ALL" BashScripts/statics_docker_with_runtime.sh

# kata + CLH
sudo kata-manager -S clh
OUT_DIR=results/out/kata_clh  RUNTIME=io.containerd.kata.v2 ITER="$ITER_ALL" BashScripts/statics_docker_with_runtime.sh

# kata + FC
sudo kata-manager -S fc

echo "Done."



