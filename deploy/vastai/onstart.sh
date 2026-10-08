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
# pinned to a commit: sf-smartfabric is not on PyPI yet; replace with a release tag
pip install --no-cache-dir "git+https://github.com/SmartTasksOrg/sf-smartfabric@e0d9eb95ec011678c183ac2b9ace2d2fa461b217"
exec sf-smartfabric serve --host 0.0.0.0 --port "$PORT"
