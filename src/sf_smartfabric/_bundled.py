"""Read the files SmartFabric ships with: the fingerprint schema, the example fleet and the
behavioural vectors.

The normative copies live at the repository root (``schema/``, ``examples/``, ``spec/vectors/``).
The wheel carries identical copies under ``sf_smartfabric/data/`` (``tests/test_bundled_data.py``
fails if they differ), so the same calls work from a PyPI install and from a clone.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path


def read_text(*parts: str) -> str:
    """Return the text of a bundled file, e.g. ``read_text("schema", "fingerprint.schema.json")``.

    Looks in the installed package first (``sf_smartfabric/data/...``), then walks up from this
    file to the repository root (a source checkout). Raises FileNotFoundError if neither has it."""
    try:
        ref = resources.files("sf_smartfabric").joinpath("data", *parts)
        if ref.is_file():
            return ref.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError, AttributeError):
        pass
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent.joinpath(*parts)
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError("/".join(parts))
