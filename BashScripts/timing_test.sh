#!/bin/sh

#read first argument 
TARGET_PAGE=$1
TARGET_PATH="/usr/sbin/nginx-debug"

if [ ! -z $2 ]; then
   TARGET_PATH=$2
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
done

echo "========> Last page of $TARGET_PATH is now loaded in the page cache."
echo -e "\n---> [infected_2]: ./spy_on_diff $TARGET_PATH"
LD_BIND_NOW=1 ./spy_on_diff $TARGET_PATH 
echo -e "========> infected_2 has received the message from infected_1.\n"