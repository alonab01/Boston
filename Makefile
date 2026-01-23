
all: spy_on read_page spy_on_diff

dkr: 
	sudo docker build -t union-buster .

dkr-run: dkr
	sudo docker rm -f gv1 || true
	sudo docker run --runtime=runsc-kvm -d --name gv1 union-buster:latest

dkr-native-run: dkr
	sudo docker rm -f gv1 || true
	sudo docker run --runtime=runc -d --name gv1 union-buster:latest

dkr-exec: 
	sudo docker exec -it gv1 /bin/bash

spy_on: spy_on.c
	gcc -o spy_on spy_on.c

spy_on_diff: spy_on_diff.c
	gcc -o spy_on_diff spy_on_diff.c

read_page: read_page.c
	gcc -o read_page read_page.c

clean:
	rm -f spy_on read_page spy_on_diff