#!/usr/bin/bash
# Script to reproduce the main results locally.
#
# Author: Novak Boskov <boskov@bu.edu>
# Date: February 2022.

TARGET_PAGE=0 # default value

#overload default values if arguments are provided
if [ ! -z "$1" ]; then
    TARGET_PAGE=$1
fi

RUNTIME=runsc

#overload default runtime if provided
if [ ! -z "$2" ]; then
    RUNTIME=$2
fi


set -e

docker --version

echo "Running the two containers..."
IMAGE_PATH=union-buster:latest
CONTAINER_NAMES=(infected_1 infected_2)
for n in ${CONTAINER_NAMES[@]}; do
    echo "sudo docker run --runtime=$RUNTIME -d --name ${n} $IMAGE_PATH"
    sudo docker run --runtime=$RUNTIME -d --name ${n} $IMAGE_PATH
done

echo -e "\n------------------------------ CONTAINERS ------------------------------"
sudo docker container ls
echo -e "------------------------------------------------------------------------\n"


echo -e "\nEvicting page cache on the host..."
sync
echo 1 | sudo tee -a /proc/sys/vm/drop_caches
echo "========> Entire OS Page Cache is now evicted."

echo -e "\n---> [infected_2]: /workspace/spy_on_diff  /usr/sbin/nginx-debug"
sudo docker exec -it infected_2 /workspace/spy_on_diff  /usr/sbin/nginx-debug 
echo -e "========> infected_2 has received the message from infected_1.\n"



echo -e "\nEvicting page cache on the host..."
sync
echo 1 | sudo tee -a /proc/sys/vm/drop_caches
echo "========> Entire OS Page Cache is now evicted."

echo -e "\n---> [infected_1]: /workspace/read_page /usr/sbin/nginx-debug $TARGET_PAGE"
sudo docker exec -it infected_1 /workspace/read_page /usr/sbin/nginx-debug $TARGET_PAGE
echo "========> page $TARGET_PAGE of /usr/sbin/nginx-debug is now loaded in the page cache."
echo -e "\n---> [infected_2]: /workspace/spy_on_diff  /usr/sbin/nginx-debug"
sudo docker exec -it infected_2 /workspace/spy_on_diff  /usr/sbin/nginx-debug 
echo -e "========> infected_2 has received the message from infected_1.\n"

echo "Cleanup..."
sudo docker rm -f infected_1 infected_2
echo "Done."
