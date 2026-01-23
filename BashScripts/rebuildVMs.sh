#!/bin/bash
VM_PATH="/home/fwilke/edu/BU/ec721"


#start base VM
sudo qemu-system-x86_64 \
-enable-kvm \
-m 2048 \
-drive file=$VM_PATH/base.qcow2,if=virtio \
-boot c \
-nic user,hostfwd=tcp:127.0.0.1:2222-:22&

sleep 20  # wait for VM to boot up

#pull git repo again and rebuild unionbuster
ssh -p 2222 root@localhost << EOF
    cd ~/unionbuster
    git pull
    make clean
    make
EOF


#shutdown base VM
ssh -p 2222 root@localhost << EOF
    poweroff
EOF
sleep 5

#show running qemu processes
echo -e "\nRunning QEMU processes:"
pgrep -fa 'qemu-system-x86_64.*vm.*.qcow2'
echo ""

#clone base VM to vmA and vmB
sudo rm -f $VM_PATH/vmA.qcow2
sudo rm -f $VM_PATH/vmB.qcow2

sudo qemu-img create -f qcow2 -b $VM_PATH/base.qcow2 -F qcow2 $VM_PATH/vmA.qcow2
sudo qemu-img create -f qcow2 -b $VM_PATH/base.qcow2 -F qcow2 $VM_PATH/vmB.qcow2