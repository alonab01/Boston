
FROM nginx:1.20.1

# Switch to Debian archived repositories for EOL buster
RUN sed -i 's|deb.debian.org|archive.debian.org|g' /etc/apt/sources.list && \
    sed -i 's|security.debian.org|archive.debian.org|g' /etc/apt/sources.list && \
    sed -i '/deb.*buster-updates/d' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y build-essential nano && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


WORKDIR /workspace
COPY . /workspace

RUN make

CMD ["nginx", "-g", "daemon off;"]


#how to build and run:
# docker build -t union-buster .
# sudo docker run --runtime=runsc -d --name gv1 union-buster:latest