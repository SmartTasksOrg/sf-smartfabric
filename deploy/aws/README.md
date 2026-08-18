# AWS deploy

Fastest path (single node):

1. Launch a `t3.micro` (free-tier) with Amazon Linux 2023.
2. Paste `user-data.sh` into **Advanced details → User data**.
3. Security group: allow inbound TCP **8770** (restrict the source CIDR — don't
   leave it 0.0.0.0/0 in production).
4. `smartfabric live --url http://<public-ip>:8770` to verify.

For more than a demo: put the node behind an ALB with ACM TLS, run it as an ECS
service, and add the registry/mTLS fabric services (docs/04). The container image
is the same one built by `deploy/Dockerfile`.
