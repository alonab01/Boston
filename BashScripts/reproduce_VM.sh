#!/usr/bin/bash
# Script to reproduce the main results locally.
#
# Author: Novak Boskov <boskov@bu.edu>
# Date: February 2022.

set -e

docker --version

echo "Compiling programs..."
# PROGRAMS=(spy_on listen_on_pcache read_page)
PROGRAMS=(spy_on read_page)
# for p in ${PROGRAMS[@]}; do
#     gcc -o ${p} ${p}.c
# done

echo "Running the two containers..."
# IMAGE_PATH=cacheattack.azurecr.io/cacheattack/nginx_infected:1.20.1-14
# IMAGE_PATH=nginx:1.20.1
IMAGE_PATH=nginx_infected_local:latest
CONTAINER_NAMES=(infected_1 infected_2)
for n in ${CONTAINER_NAMES[@]}; do
    sudo docker run --runtime=runc -d --name ${n} $IMAGE_PATH
    # sudo docker run -d --name ${n} $IMAGE_PATH
    # for p in ${PROGRAMS[@]}; do
    #     sudo docker cp ${p} ${n}:/
    # done
done
echo -e "\n------------------------------ CONTAINERS ------------------------------"
sudo docker container ls
echo -e "------------------------------------------------------------------------\n"

echo -e "\nEvicting page cache on the host..."
sync
echo 1 | sudo tee -a /proc/sys/vm/drop_caches
echo "========> Entire OS Page Cache is now evicted."

echo -e "\n---> [infected_1]: /spy_on /usr/sbin/nginx-debug"
sudo docker exec -it infected_1 /spy_on /usr/sbin/nginx-debug
echo "========> This means that /usr/sbin/nginx-debug is not in the page cache from the standpoint of infected_1."
echo -e "\n---> [infected_2]: /spy_on /usr/sbin/nginx-debug"
sudo docker exec -it infected_2 /spy_on /usr/sbin/nginx-debug
echo "========> This means that /usr/sbin/nginx-debug is not in the page cache from the standpoint of infected_2"

echo -e "\n---> [infected_1]: /read_page /usr/sbin/nginx-debug 0"
sudo docker exec -it infected_1 /read_page /usr/sbin/nginx-debug 0
echo "========> Last page of /usr/sbin/nginx-debug is now loaded in the page cache."
echo -e "\n---> [infected_2]: /spy_on /usr/sbin/nginx-debug"
sudo docker exec -it infected_2 /spy_on /usr/sbin/nginx-debug
echo -e "========> infected_2 has received the message from infected_1.\n"

echo "Cleanup..."
sudo docker rm -f infected_1 infected_2
echo "Done."
