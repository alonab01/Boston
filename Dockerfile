ARG BASE_IMAGE=weaveworks/ignite-ubuntu:latest
ARG TOOL=read_page
ARG SRC_DIR=src

# ---------- build stage ----------
FROM ${BASE_IMAGE} AS build
ARG TOOL
ARG SRC_DIR

RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# Copy ONLY the selected file
COPY ${SRC_DIR}/${TOOL}.c ./

# Make output dir, then compile
RUN set -eux; \
    mkdir -p /out; \
    gcc -O2 -Wall -Wextra "${TOOL}.c" -o "/out/${TOOL}"

# ---------- final stage ----------
FROM ${BASE_IMAGE}
ARG TOOL
COPY --from=build "/out/${TOOL}" "/usr/local/bin/${TOOL}"
