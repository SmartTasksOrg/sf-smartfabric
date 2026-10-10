#!/bin/bash
# vast.ai on-start script for a SmartFabric node.
#
# vast.ai rents GPU boxes and runs a Docker image you specify. That's exactly the
# unit this deploys — the node runs fine on a GPU host (it governs GPU-backed AI
# nodes; it doesn't itself need the GPU). Point vast at the published image and use
# this as the on-start command, OR paste the body into the on-start field.
#
# The node's value on a GPU box: it's the containment plane co-located with the
# model workers it meters, so pressure/consent enforcement sits next to the
# compute it governs.
set -e
PORT="${SMARTFABRIC_PORT:-8770}"
# If the image already has sf-smartfabric installed, just run it:
if command -v sf-smartfabric >/dev/null 2>&1; then
  exec sf-smartfabric serve --host 0.0.0.0 --port "$PORT"
fi
# Otherwise install from the repository at a fixed commit and run (for a generic CUDA/python base image).
# pinned to the reviewed release; published only by SmartTasksOrg/sf-smartfabric, with provenance
pip install --no-cache-dir "sf-smartfabric==0.5.1"
exec sf-smartfabric serve --host 0.0.0.0 --port "$PORT"
