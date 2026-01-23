#!/bin/bash
#
# Author: Novak Boskov <boskov@bu.edu>
# Date: February 2022.

set -e

PROGRAM_PATH=Examples/
POD=nginx-1-7f8989c859-5hlpb
C1=nginx-infected-1
C2=nginx-infected-2

kubectl get pod

if ! [ -e spy_on ] || ! [ -e read_page ]; then
    echo -e "Compiling executables locally...\n"
    gcc -o spy_on $PROGRAM_PATH/spy_on.c
    gcc -o read_page $PROGRAM_PATH/read_page.c
fi

echo -e "\nCopying to the containers...\n"
kubectl cp spy_on ${POD}:/ -c ${C1}
kubectl cp read_page ${POD}:/ -c ${C1}
kubectl cp spy_on ${POD}:/ -c ${C2}
kubectl cp read_page ${POD}:/ -c ${C2}

echo -e "\n---> [${C1}]: ./spy_on /usr/sbin/nginx-debug"
kubectl exec -it ${POD} -c ${C1} -- ./spy_on /usr/sbin/nginx-debug
echo "========> This means that /usr/sbin/nginx-debug is not in the page cache from the standpoint of ${C1}."
echo -e "\n---> [${C2}]: ./spy_on /usr/sbin/nginx-debug"
kubectl exec -it ${POD} -c ${C2} -- ./spy_on /usr/sbin/nginx-debug
echo "========> This means that /usr/sbin/nginx-debug is not in the page cache from the standpoint of ${C2}"

echo -e "\n---> [${C1}]: ./read_page /usr/sbin/nginx-debug 0"
kubectl exec -it ${POD} -c ${C1} -- ./read_page /usr/sbin/nginx-debug 0
echo "========> Last page of /usr/sbin/nginx-debug is now loaded in the page cache."
echo -e "\n---> [${C2}]: ./spy_on /usr/sbin/nginx-debug"
kubectl exec -it ${POD} -c ${C2} -- ./spy_on /usr/sbin/nginx-debug
echo -e "========> ${C2} has received the message from ${C1}.\n"
