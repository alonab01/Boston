#!/bin/bash
VM_PATH="/home/alonab01/vms"
USER="alonab01"
TARGET_FILE="results/txt/qemu_p0_50.txt"
TARGET_PAGE_RANGE="0"


echo -e "\nStarting two VMs (vmA and vmB)..."

qemu-system-x86_64 \
-enable-kvm \
-m 2048 \
-drive file=$VM_PATH/vmA.qcow2,if=virtio \
-boot c \
-nic user,hostfwd=tcp:127.0.0.1:2222-:22&

qemu-system-x86_64 \
-enable-kvm \
-m 2048 \
-drive file=$VM_PATH/vmB.qcow2,if=virtio \
-boot c \
-nic user,hostfwd=tcp:127.0.0.1:2223-:22&


sleep 60  # wait for VMs to boot up



# first section - vmA reads directly from the disk

ssh -p 2222 $USER@localhost  << EOF
sync
echo 1 | tee -a /proc/sys/vm/drop_caches 
EOF

ssh -p 2223 $USER@localhost  << EOF
sync
echo 1 | tee -a /proc/sys/vm/drop_caches 
EOF

echo -e "\nEvicting page cache on the host..."
sync
echo 1 | sudo tee -a /proc/sys/vm/drop_caches


echo -e "Starting section 1 - vmA reads from "disk" "


 for i in {1..3}; do

    echo -e "vmA read:"
    ssh -p 2222 $USER@localhost << EOF
    cd ~/Documents/Boston
    ./read_page $TARGET_FILE -p $TARGET_PAGE_RANGE
    sync
    echo 1 | tee -a /proc/sys/vm/drop_caches 
EOF


    echo -e "\nEvicting page cache on the host..."
    sync
    echo 1 | sudo tee -a /proc/sys/vm/drop_caches
 done



 # second section - vmA reads after vmB reads-> supose to be from host page cache

echo -e "Starting section 1 - vmA reads from "host page cache" "

 for i in {1..3}; do
    echo -e "vmB read:"
    ssh -p 2223 $USER@localhost << EOF
    cd ~/Documents/Boston
    ./read_page $TARGET_FILE -p $TARGET_PAGE_RANGE
    sync
    echo 1 | tee -a /proc/sys/vm/drop_caches 
EOF

    echo -e "vmA read:"
    ssh -p 2222 $USER@localhost  << EOF
    cd ~/Documents/Boston
    ./read_page $TARGET_FILE -p $TARGET_PAGE_RANGE
    sync
    echo 1 | tee -a /proc/sys/vm/drop_caches 
EOF


    echo -e "\nEvicting page cache on the host..."
    sync
    echo 1 | sudo tee -a /proc/sys/vm/drop_caches
 done


#shutdown vmA
ssh -p 2222  $USER@localhost << EOF
    sudo poweroff
EOF
sleep 5

#shutdown vmB
ssh -p 2223  $USER@localhost << EOF
    sudo poweroff
EOF
sleep 5


    ssh -p 2222 $USER@localhost  << EOF
    cd ~/Documents/Boston
    ./read_page $TARGET_FILE -p $TARGET_PAGE_RANGE

EOF




    ssh -p 2222 $USER@localhost  << EOF
    sync
    echo 1 | sudo tee -a /proc/sys/vm/drop_caches 

EOF
