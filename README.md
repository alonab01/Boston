
sudo sync
 echo 1|sudo tee /proc/sys/vm/drop_caches
 echo 3|sudo tee /proc/sys/vm/drop_caches

START QEMU:
qemu-system-x86_64   -enable-kvm   -m 4096   -smp 2   -drive file=~/vms/vm2.qcow2,format=qcow2  -cpu host
GENARATE QEMU:
qemu-system-x86_64   -enable-kvm   -m 4096   -smp 2   -cdrom ~/iso/ubuntu-22.04.5-desktop-amd64.iso   -drive file=~/vms/vm2.qcow2,format=qcow2   -boot d   -display gtk

GYVISOR:
docker run -d --name prober-kvm2 --runtime=runsc-kvm  lab-prober:mysql84 bash -lc "sleep infinity"
docker run -d --name prober-systrap2 --runtime=runsc-systrap lab-prober:mysql84 bash -lc "sleep infinity"

DOCKER:
delete:
docker rm -f $(docker ps -aq) 
docker rmi IMAGE_ID


IGNITE:
docker build -f Dockerfile --build-arg BASE_IMAGE=weaveworks/ignite-ubuntu:latest --build-arg TOOL=detection -t ignite_prober .
docker save ignite_prober:latest | sudo ctr -n firecracker images import -
sudo ctr -n firecracker images ls | grep ignite_prober
sudo ignite image import ignite_prober:latest


VENV:
source .venv/bin/activate
deactivate


STUFF:
> /dev/null