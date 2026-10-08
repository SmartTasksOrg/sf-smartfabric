#!/bin/bash
# Alternative: plain Droplet via docker (docker-image based, like the cloud VMs).
apt-get update -y && apt-get install -y docker.io
systemctl enable --now docker
docker run -d --restart always -p 8770:8770 --name smartfabric-node \
  ghcr.io/smarttasksorg/sf-smartfabric:latest
