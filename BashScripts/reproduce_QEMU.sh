#!/usr/bin/bash
# Script to reproduce the main results locally.
#
# Author: Novak Boskov <boskov@bu.edu>
# Date: February 2022.

TARGET_PAGE=0 # default value
TARGET_PATH="../runsc" # default value
VM_PATH="/home/fwilke/edu/BU/ec721"
MEASURE_PAGE_COUNT=2


#overload default values if arguments are provided
if [ ! -z "$1" ]; then
    TARGET_PAGE=$1
fi

if [ ! -z "$2" ]; then
    TARGET_PATH=$2
fi

set -e

# start two VMs if $4 set

if [ ! -z "$4" ]; then
    echo -e "\nStarting two VMs (vmA and vmB)..."

    sudo qemu-system-x86_64 \
    -enable-kvm \
    -m 2048 \
    -drive file=$VM_PATH/vmA.qcow2,if=virtio \
    -boot c \
    -nic user,hostfwd=tcp:127.0.0.1:2222-:22&

    sudo qemu-system-x86_64 \
    -enable-kvm \
    -m 2048 \
    -drive file=$VM_PATH/vmB.qcow2,if=virtio \
    -boot c \
    -nic user,hostfwd=tcp:127.0.0.1:2223-:22&


    sleep 20  # wait for VMs to boot up
fi



echo -e "\nEvicting page cache on the host..."
sync
echo 1 | sudo tee -a /proc/sys/vm/drop_caches
echo "========> Entire OS Page Cache is now evicted."



#only prime if $3 is set
if [ ! -z "$3" ]; then
    # run read_page /usr/sbin/nginx-debug $TARGET_PAGE in VM1
    echo -e "\n---> [VM1]: ./read_page $TARGET_PATH $TARGET_PAGE"

    ssh -p 2222 root@localhost << EOF
    echo 1 | tee -a /proc/sys/vm/drop_caches

    cd ~/unionbuster
    LD_BIND_NOW=1 ./read_page $TARGET_PATH $TARGET_PAGE
EOF

fi

echo -e "\n---> [VM2]: ./spy_on $TARGET_PATH $MEASURE_PAGE_COUNT"

ssh -p 2223 root@localhost << EOF
echo 1 | tee -a /proc/sys/vm/drop_caches

cd ~/unionbuster
LD_BIND_NOW=1 ./spy_on $TARGET_PATH $MEASURE_PAGE_COUNT
EOF

echo "Done."
