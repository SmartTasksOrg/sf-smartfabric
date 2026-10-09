#!/bin/bash
# EC2 user-data: boot a SmartFabric node on Amazon Linux 2023 (t3.micro free tier).
# Attach a security group that opens TCP 8770 (restrict the source in production).
dnf update -y
dnf install -y docker
systemctl enable --now docker
docker run -d --restart always -p 8770:8770 --name smartfabric-node \
  ghcr.io/smarttasksorg/sf-smartfabric:0.5.0
