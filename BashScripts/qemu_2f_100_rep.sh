#!/bin/bash
COMMAND="./reproduce_QEMU.sh 0"
TARGET_FILES=("../rand0.bin" "../rand1.bin")
VM_PATH="/home/fwilke/edu/BU/ec721"
MEASURE_PAGE_COUNT=1
TARGET_PAGE=0


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



for secret in {0..3}; do  
    for i in {1..100}; do
        echo -e "\nEvicting page cache on the host..."
        sync
        echo 1 | sudo tee -a /proc/sys/vm/drop_caches
        echo "========> Entire OS Page Cache is now evicted."



        #iterate over target files  
        for index in {0..1}; do
            TARGET_FILE=${TARGET_FILES[$index]}
            #prime file if the secret's bit at the index of the target file is 1
            ((bit = (secret >> index) & 1 ))
            if [ $bit -eq 1 ]; then
                echo -e "\nPriming file $TARGET_FILE for secret $secret (bit $index is 1)..."

                echo -e "\n---> [VM1]: ./read_page $TARGET_FILE $TARGET_PAGE"

                ssh -p 2222 root@localhost << EOF
                echo 1 | tee -a /proc/sys/vm/drop_caches

                cd ~/unionbuster
                LD_BIND_NOW=1 ./read_page $TARGET_FILE $TARGET_PAGE
EOF

            else
                echo "Not priming file $TARGET_FILE for secret $secret (bit $index is 0)."
            fi
        done
        
        
        echo -e "\n---> [VM2]: ./spy_on ${TARGET_FILES[0]} $MEASURE_PAGE_COUNT"
        echo -e "\n---> [VM2]: ./spy_on ${TARGET_FILES[1]} $MEASURE_PAGE_COUNT"

        ssh -p 2223 root@localhost << EOF
        echo 1 | tee -a /proc/sys/vm/drop_caches

        cd ~/unionbuster
        LD_BIND_NOW=1 ./spy_on ${TARGET_FILES[0]} $MEASURE_PAGE_COUNT
        LD_BIND_NOW=1 ./spy_on ${TARGET_FILES[1]} $MEASURE_PAGE_COUNT
EOF
    done
done
